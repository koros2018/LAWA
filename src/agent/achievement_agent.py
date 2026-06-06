"""
AchievementAgent — 成就系统

管理：成就列表/进度追踪/自动解锁/徽章展示
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select, and_
from src.database.main import AsyncSessionLocal
from src.database.session import get_async_session
from src.models.achievement import (
    Achievement, UserAchievement, Badge, ALL_ACHIEVEMENTS,
)
from src.models.user import LawaProfile
from src.models.coin import CoinTransaction
from src.agent.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AchievementAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="AchievementAgent")

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "")
        handlers = {
            "list": self.list_all,
            "my": self.my_achievements,
            "track": self.track_progress,
            "badges": self.my_badges,
            "check_unlock": self.check_and_unlock,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        try:
            result = await handler(payload)
            self.log_execution(payload, result)
            return result
        except Exception as e:
            logger.error(f"AchievementAgent error: {e}")
            return {"error": str(e)}

    # ── 全部成就列表 ──

    async def list_all(self, payload: dict) -> dict:
        user_id = payload.get("user_id")
        category = payload.get("category", "all")
        async with get_async_session() as session:
            # 确保种子数据已入库
            await self._seed_achievements(session)

            query = select(Achievement)
            if category != "all":
                query = query.where(Achievement.category == category)
            result = await session.execute(query.order_by(Achievement.category, Achievement.tier))
            achievements = result.scalars().all()

            # 获取用户进度
            user_achs = {}
            if user_id:
                ua_result = await session.execute(
                    select(UserAchievement).where(UserAchievement.user_id == user_id)
                )
                for ua in ua_result.scalars().all():
                    user_achs[str(ua.achievement_id)] = ua

            items = []
            for a in achievements:
                ua = user_achs.get(str(a.id))
                items.append({
                    "id": str(a.id), "code": a.code, "name": a.name, "emoji": a.emoji,
                    "description": a.description, "category": a.category, "tier": a.tier,
                    "xp_reward": a.xp_reward, "coin_reward": a.coin_reward,
                    "requirement_desc": a.requirement_desc,
                    "progress": ua.progress if ua else 0,
                    "completed": bool(ua.completed) if ua else False,
                    "completed_at": ua.completed_at.isoformat() if ua and ua.completed_at else None,
                    "hidden": bool(a.hidden) and (not ua or not ua.completed),
                })

            return {"achievements": items, "count": len(items), "completed": sum(1 for i in items if i["completed"])}

    # ── 我的成就 ──

    async def my_achievements(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        return await self.list_all({"user_id": user_id})

    # ── 进度追踪 ──

    async def track_progress(self, payload: dict) -> dict:
        """通用进度追踪入口——由其他Agent调用
        例如：完成一个任务 → track_progress(user_id, type="counter", code="quest_10", value=1)
        """
        user_id = payload["user_id"]
        track_type = payload.get("type", "counter")  # counter/reach/collect/streak
        track_code = payload.get("code", "")          # 对应的成就code
        track_value = payload.get("value", 1)

        async with get_async_session() as session:
            await self._seed_achievements(session)

            # 找匹配的成就
            result = await session.execute(
                select(Achievement).where(Achievement.requirement_type == track_type)
            )
            unlocked = []

            for ach in result.scalars().all():
                if track_code and ach.code != track_code:
                    continue
                # 获取或创建用户进度
                ua_result = await session.execute(
                    select(UserAchievement).where(
                        and_(UserAchievement.user_id == user_id, UserAchievement.achievement_id == ach.id)
                    )
                )
                ua = ua_result.scalar_one_or_none()
                if not ua:
                    ua = UserAchievement(user_id=user_id, achievement_id=ach.id, progress=0)
                    session.add(ua)

                if ua.completed:
                    continue

                # 更新进度
                ua.progress += track_value
                if ua.progress >= ach.requirement_value:
                    ua.completed = 1
                    ua.completed_at = datetime.now(timezone.utc)
                    # 发放奖励
                    profile = await self._get_profile(session, user_id)
                    if profile:
                        profile.xp = (profile.xp or 0) + ach.xp_reward
                        profile.total_coins = (profile.total_coins or 0) + ach.coin_reward
                    unlocked.append({
                        "code": ach.code, "name": ach.name, "emoji": ach.emoji,
                        "xp": ach.xp_reward, "coin": ach.coin_reward,
                    })

            await session.commit()

            return {
                "tracked": True,
                "unlocked": unlocked,
                "unlocked_count": len(unlocked),
            }

    # ── 徽章 ──

    async def my_badges(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        async with get_async_session() as session:
            await self._seed_achievements(session)

            # 获取完成的成就
            completed_result = await session.execute(
                select(UserAchievement).where(
                    and_(UserAchievement.user_id == user_id, UserAchievement.completed == 1)
                )
            )
            completed_ids = {str(ua.achievement_id) for ua in completed_result.scalars().all()}

            # 获取对应成就的badge_code
            badges = []
            ach_result = await session.execute(
                select(Achievement).where(Achievement.id.in_(completed_ids))
            )
            for ach in ach_result.scalars().all():
                if ach.badge_code:
                    badge = await session.execute(
                        select(Badge).where(Badge.code == ach.badge_code)
                    )
                    b = badge.scalar_one_or_none()
                    badges.append({
                        "code": ach.badge_code,
                        "name": b.name if b else ach.badge_code,
                        "emoji": b.emoji if b else "🏅",
                        "from_achievement": ach.name,
                    })

            return {"badges": badges, "count": len(badges), "user_id": user_id}

    # ── 批量检查 ──

    async def check_and_unlock(self, payload: dict) -> dict:
        """批量检查所有可能的成就解锁"""
        user_id = payload["user_id"]
        async with get_async_session() as session:
            profile = await self._get_profile(session, user_id)
            if not profile:
                return {"error": "用户画像不存在"}

            await self._seed_achievements(session)

            # 检查各类型成就
            checks = []

            # reach型: 学习时间/等级
            for ach_code, val in [
                ("study_10h", profile.total_study_minutes or 0),
                ("study_50h", profile.total_study_minutes or 0),
                ("level_10", profile.level or 0),
                ("level_50", profile.level or 0),
                ("streak_7", profile.consecutive_login_days or 0),
                ("streak_30", profile.consecutive_login_days or 0),
            ]:
                r = await self.track_progress({
                    "user_id": user_id, "type": "reach", "code": ach_code, "value": val,
                })
                checks.extend(r.get("unlocked", []))

            return {"checked": True, "newly_unlocked": checks, "count": len(checks)}

    # ── helpers ──

    async def _seed_achievements(self, session) -> None:
        existing = await session.execute(select(Achievement).limit(1))
        if existing.scalar_one_or_none():
            return
        for a in ALL_ACHIEVEMENTS:
            session.add(Achievement(**a))
        await session.commit()

    async def _get_profile(self, session, user_id):
        result = await session.execute(
            select(LawaProfile).where(LawaProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()
