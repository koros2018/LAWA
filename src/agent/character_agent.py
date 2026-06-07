"""
LAWA CharacterAgent — RPG 角色成长系统

管理经验值/等级提升/天赋分配/职业选择
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from sqlalchemy import select, update
from src.agent.base_agent import BaseAgent
from src.database import AsyncSessionLocal

from src.models.user import LawaProfile
# ── 等级公式 ──
def xp_to_level(xp: int) -> int:
    """level = floor(sqrt(xp / 100)) + 1, max 100"""
    import math
    return min(100, int(math.sqrt(max(0, xp) / 100)) + 1)

def xp_for_level(level: int) -> int:
    """到达某等级所需的最小XP"""
    return 100 * (level - 1) ** 2
# ── 职业定义 ──
CHARACTER_CLASSES = {
    "entrepreneur": {"name": "创业者", "desc": "翻译/转换/资源整合", "bonus": "互助任务 +20%"},
    "finance": {"name": "金融从业者", "desc": "教学/纠错/分析", "bonus": "帮助收益 +25%"},
    "engineer": {"name": "工程师", "desc": "写作/创作/构建", "bonus": "写作任务 +30%"},
    "internet_observer": {"name": "互联网观察员", "desc": "口语/文化/趋势", "bonus": "文化探索 +40%"},
    "international_observer": {"name": "国际观察员", "desc": "综合/谈判/视野", "bonus": "全任务 +10%"},
}

# ── XP来源定义 ──
XP_SOURCES = {
    "study_10min": 5,
    "daily_quest": 20,
    "help_others": 15,
    "dungeon_clear": 50,
    "zone_unlock": 100,
    "login_streak_7": 50,
    "guild_contribute": 10,
}

# ── 每日XP上限 ──
DAILY_XP_CAP = 500
class CharacterAgent(BaseAgent):
    """角色成长Agent"""

    def __init__(self):
        super().__init__("CharacterAgent")

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "get_profile")
        handlers = {
            "get_profile": self.get_profile,
            "add_xp": self.add_xp,
            "get_xp": self.get_xp,
            "choose_class": self.choose_class,
            "allocate_talent": self.allocate_talent,
            "set_title": self.set_title,
            "get_stats": self.get_stats,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"未知操作: {action}"}
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    # ── 获取角色面板 ──
    async def get_profile(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LawaProfile).where(LawaProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return {"error": "用户画像不存在，请先完成评估"}
            
            return {
                "user_id": str(profile.user_id),
                "character_class": profile.character_class,
                "class_info": CHARACTER_CLASSES.get(profile.character_class, {}) if profile.character_class else None,
                "xp": profile.xp,
                "level": profile.level,
                "xp_to_next_level": xp_for_level(profile.level + 1) - profile.xp,
                "talent_points": profile.talent_points,
                "skill_tree": profile.skill_tree,
                "title": profile.title,
                "avatar_config": profile.avatar_config,
            }

    # ── 获取XP ──
    async def get_xp(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LawaProfile.xp, LawaProfile.level).where(LawaProfile.user_id == user_id)
            )
            row = result.one_or_none()
            if not row:
                return {"error": "用户不存在"}
            xp, level = row
            return {
                "xp": xp,
                "level": level,
                "xp_to_next": xp_for_level(level + 1) - xp,
                "total_for_next": xp_for_level(level + 1),
            }

    # ── 增加经验值 ──
    async def add_xp(self, payload: dict) -> dict:
        """增加经验值，自动处理升级"""
        user_id = payload["user_id"]
        source = payload.get("source", "study_10min")
        amount = payload.get("amount", XP_SOURCES.get(source, 5))
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LawaProfile).where(LawaProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return {"error": "用户不存在"}
            
            # 每日上限检查
            # (简化版：仅检查来源是否为study；完整版需daily_tracker表)
            if source == "study_10min":
                # 单日学习奖励上限简化为12次 (=60 XP/day from study)
                pass
            
            old_xp = profile.xp
            old_level = profile.level
            new_xp = old_xp + amount
            new_level = xp_to_level(new_xp)
            
            profile.xp = new_xp
            profile.level = new_level
            
            # 升级处理
            leveled_up = new_level > old_level
            talent_gained = 0
            if leveled_up:
                talent_gained = new_level - old_level  # 每级1点
                profile.talent_points += talent_gained
                logger.info(f"🎉 {user_id[:8]} 升级! Lv{old_level} → Lv{new_level} (+{talent_gained}天赋点)")
            
            await session.commit()
            
            return {
                "status": "ok",
                "source": source,
                "xp_added": amount,
                "old_xp": old_xp,
                "new_xp": new_xp,
                "old_level": old_level,
                "new_level": new_level,
                "leveled_up": leveled_up,
                "talent_gained": talent_gained,
                "xp_to_next": xp_for_level(new_level + 1) - new_xp if new_level < 100 else 0,
            }

    # ── 选择职业 ──
    async def choose_class(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        class_key = payload.get("class_key")
        
        if class_key not in CHARACTER_CLASSES:
            return {"error": f"无效职业: {class_key}", "available": list(CHARACTER_CLASSES.keys())}
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LawaProfile).where(LawaProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return {"error": "用户不存在"}
            
            profile.character_class = class_key
            await session.commit()
            
            logger.info(f"🎭 {user_id[:8]} 选择职业: {CHARACTER_CLASSES[class_key]['name']}")
            return {
                "status": "ok",
                "character_class": class_key,
                "class_info": CHARACTER_CLASSES[class_key],
            }

    # ── 分配天赋点 ──
    async def allocate_talent(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        skill = payload.get("skill")  # "grammar" | "reading" | "writing" | "speaking"
        points = payload.get("points", 1)
        
        valid_skills = ["grammar", "reading", "writing", "speaking"]
        if skill not in valid_skills:
            return {"error": f"无效技能: {skill}", "available": valid_skills}
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LawaProfile).where(LawaProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return {"error": "用户不存在"}
            
            if profile.talent_points < points:
                return {"error": f"天赋点不足 (可用: {profile.talent_points}, 需要: {points})"}
            
            skill_tree = dict(profile.skill_tree or {})
            old_level = skill_tree.get(skill, 0)
            new_level = old_level + points
            
            if new_level > 5:
                return {"error": f"{skill} 已达上限 (5级)"}
            
            skill_tree[skill] = new_level
            profile.skill_tree = skill_tree
            profile.talent_points -= points
            
            await session.commit()
            
            logger.info(f"⭐ {user_id[:8]} 分配天赋: {skill} Lv{old_level}→Lv{new_level}")
            return {
                "status": "ok",
                "skill": skill,
                "old_level": old_level,
                "new_level": new_level,
                "remaining_talent": profile.talent_points,
                "skill_tree": skill_tree,
            }

    # ── 设置称号 ──
    async def set_title(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        title = payload.get("title", "")
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LawaProfile).where(LawaProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return {"error": "用户不存在"}
            
            old_title = profile.title
            profile.title = title
            await session.commit()
            
            return {"status": "ok", "old_title": old_title, "new_title": title}

    # ── 获取统计 ──
    async def get_stats(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(LawaProfile).where(LawaProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return {"error": "用户不存在"}
            
            return {
                "user_id": str(profile.user_id),
                "level": profile.level,
                "xp": profile.xp,
                "xp_progress_pct": round(
                    (profile.xp - xp_for_level(profile.level)) / 
                    max(1, xp_for_level(profile.level + 1) - xp_for_level(profile.level)) * 100, 1
                ) if profile.level < 100 else 100.0,
                "class": profile.character_class,
                "title": profile.title,
                "skill_tree": profile.skill_tree,
                "talent_unspent": profile.talent_points,
                "total_study_minutes": profile.total_study_minutes,
                "total_coins": profile.total_coins,
            }
