"""
LAWA RPG 成就系统

Achievement: 成就模板（里程碑/挑战/收藏）
UserAchievement: 用户成就记录
Badge: 徽章（展示在角色面板）
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, JSON, ForeignKey, DateTime, Float
from src.database import Base


def _newid() -> str:
    return str(uuid.uuid4())


class Achievement(Base):
    """成就模板"""
    __tablename__ = "achievements"

    id = Column(String(36), primary_key=True, default=_newid)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(80), nullable=False)
    emoji = Column(String(5), default="🏆")
    description = Column(Text, default="")
    category = Column(String(20), nullable=False, comment="milestone/challenge/collection/social")
    tier = Column(Integer, default=1, comment="成就等级 1-5")
    xp_reward = Column(Integer, default=50)
    coin_reward = Column(Integer, default=20)
    badge_code = Column(String(20), nullable=True, comment="解锁的徽章code")
    requirement_type = Column(String(30), nullable=False, comment="counter/reach/collect/streak")
    requirement_value = Column(Integer, default=1, comment="目标值")
    requirement_desc = Column(String(200), default="", comment="达成条件描述")
    hidden = Column(Integer, default=0, comment="0可见 1隐藏(达成前不显示)")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserAchievement(Base):
    """用户成就记录"""
    __tablename__ = "user_achievements"

    id = Column(String(36), primary_key=True, default=_newid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    achievement_id = Column(String(36), ForeignKey("achievements.id"), nullable=False)
    progress = Column(Integer, default=0, comment="当前进度（counter型）")
    completed = Column(Integer, default=0, comment="0未完成 1已完成")
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Badge(Base):
    """徽章"""
    __tablename__ = "badges"

    id = Column(String(36), primary_key=True, default=_newid)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    emoji = Column(String(5), default="🏅")
    description = Column(Text, default="")
    rarity = Column(String(10), default="common")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# 成就种子 — 里程碑类
ACHIEVEMENT_MILESTONES = [
    {"code": "first_steps", "name": "初来乍到", "emoji": "👣", "category": "milestone", "tier": 1,
     "description": "完成第一次评估测试", "requirement_type": "counter", "requirement_value": 1,
     "xp_reward": 20, "coin_reward": 10, "requirement_desc": "完成评估测试"},
    {"code": "study_10h", "name": "学而不厌", "emoji": "📚", "category": "milestone", "tier": 2,
     "description": "累计学习10小时", "requirement_type": "reach", "requirement_value": 600,
     "xp_reward": 50, "coin_reward": 30, "badge_code": "scholar_bronze", "requirement_desc": "学习600分钟"},
    {"code": "study_50h", "name": "书山有路", "emoji": "🏔️", "category": "milestone", "tier": 3,
     "description": "累计学习50小时", "requirement_type": "reach", "requirement_value": 3000,
     "xp_reward": 150, "coin_reward": 80, "badge_code": "scholar_silver", "requirement_desc": "学习3000分钟"},
    {"code": "level_10", "name": "初窥门径", "emoji": "⭐", "category": "milestone", "tier": 2,
     "description": "RPG等级达到10级", "requirement_type": "reach", "requirement_value": 10,
     "xp_reward": 80, "coin_reward": 40, "requirement_desc": "达到Lv.10"},
    {"code": "level_50", "name": "一代宗师", "emoji": "👑", "category": "milestone", "tier": 5,
     "description": "RPG等级达到50级", "requirement_type": "reach", "requirement_value": 50,
     "xp_reward": 500, "coin_reward": 200, "badge_code": "grandmaster", "requirement_desc": "达到Lv.50"},
]

ACHIEVEMENT_CHALLENGES = [
    {"code": "quest_10", "name": "任务达人", "emoji": "📋", "category": "challenge", "tier": 1,
     "description": "完成10个任务", "requirement_type": "counter", "requirement_value": 10,
     "xp_reward": 30, "coin_reward": 15, "requirement_desc": "完成10个任务"},
    {"code": "quest_100", "name": "任务机器", "emoji": "⚙️", "category": "challenge", "tier": 3,
     "description": "完成100个任务", "requirement_type": "counter", "requirement_value": 100,
     "xp_reward": 200, "coin_reward": 100, "badge_code": "quest_master", "requirement_desc": "完成100个任务"},
    {"code": "perfect_5", "name": "满分选手", "emoji": "💯", "category": "challenge", "tier": 2,
     "description": "评估测试获得5次满分", "requirement_type": "counter", "requirement_value": 5,
     "xp_reward": 100, "coin_reward": 50, "requirement_desc": "评估获得5次满分"},
    {"code": "streak_7", "name": "连续七天", "emoji": "🔥", "category": "challenge", "tier": 2,
     "description": "连续7天登录学习", "requirement_type": "streak", "requirement_value": 7,
     "xp_reward": 70, "coin_reward": 35, "requirement_desc": "连续登录7天"},
    {"code": "streak_30", "name": "月之契约", "emoji": "🌙", "category": "challenge", "tier": 4,
     "description": "连续30天登录学习", "requirement_type": "streak", "requirement_value": 30,
     "xp_reward": 300, "coin_reward": 150, "badge_code": "moon_warrior", "requirement_desc": "连续登录30天"},
]

ACHIEVEMENT_SOCIAL = [
    {"code": "first_help", "name": "助人为乐", "emoji": "🤝", "category": "social", "tier": 1,
     "description": "第一次帮助别人解答问题", "requirement_type": "counter", "requirement_value": 1,
     "xp_reward": 20, "coin_reward": 10, "requirement_desc": "成功帮助1次"},
    {"code": "help_50", "name": "良师益友", "emoji": "🧑‍🏫", "category": "social", "tier": 3,
     "description": "累计帮助50人次", "requirement_type": "counter", "requirement_value": 50,
     "xp_reward": 200, "coin_reward": 100, "badge_code": "mentor", "requirement_desc": "帮助50人次"},
    {"code": "guild_join", "name": "找到组织", "emoji": "🏛️", "category": "social", "tier": 1,
     "description": "加入一个公会", "requirement_type": "counter", "requirement_value": 1,
     "xp_reward": 30, "coin_reward": 15, "requirement_desc": "加入公会"},
]

ACHIEVEMENT_COLLECTION = [
    {"code": "collect_5_eq", "name": "装备收藏家", "emoji": "🎒", "category": "collection", "tier": 1,
     "description": "收集5件装备", "requirement_type": "collect", "requirement_value": 5,
     "xp_reward": 30, "coin_reward": 20, "requirement_desc": "背包中有5件装备"},
    {"code": "collect_epic", "name": "史诗之证", "emoji": "💎", "category": "collection", "tier": 3,
     "description": "获得一件史诗级装备", "requirement_type": "counter", "requirement_value": 1,
     "xp_reward": 100, "coin_reward": 50, "badge_code": "epic_collector", "requirement_desc": "拥有1件史诗装备"},
]

ALL_ACHIEVEMENTS = ACHIEVEMENT_MILESTONES + ACHIEVEMENT_CHALLENGES + ACHIEVEMENT_SOCIAL + ACHIEVEMENT_COLLECTION
