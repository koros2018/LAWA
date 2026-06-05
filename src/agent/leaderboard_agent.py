"""
LAWA LeaderboardAgent — 排行榜系统

使用 SQLAlchemy 异步持久化存储：
- 日榜 / 周榜 / 总榜
- 学习时长榜 / 帮助榜 / 金币榜 / 任务完成榜
- 多维度排名 + 个人排名
- 日快照归档
"""
import uuid as _uuid
from datetime import date
from loguru import logger
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import AsyncSessionLocal
from src.models.leaderboard import LeaderboardEntry, LeaderboardSnapshot
from src.agent.base_agent import BaseAgent
from src.services.cache_service import cache_service, cached
from src.config import settings


class LeaderboardAgent(BaseAgent):
    """排行榜核心Agent（DB持久化版）"""

    TYPES = ["coins", "study_time", "help_count", "tasks_completed"]

    def __init__(self):
        super().__init__("LeaderboardAgent")

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "get_board")
        handlers = {
            "record": self.record_score,
            "get_board": self.get_board,
            "get_rank": self.get_rank,
            "daily_snapshot": self.daily_snapshot,
        }
        handler = handlers.get(action)
        if not handler:
            result = {"error": f"未知操作: {action}"}
            self.log_execution(payload, result)
            return result
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    # ── 记录分数 ──
    async def record_score(self, payload: dict) -> dict:
        """记录用户某项分数（upsert）"""
        user_id = _uuid.UUID(payload["user_id"]) if isinstance(payload["user_id"], str) else payload["user_id"]
        board_type = payload.get("board_type", "coins")
        score = payload.get("score", 1)

        async with AsyncSessionLocal() as session:
            for period in ["daily", "weekly", "all"]:
                stmt = select(LeaderboardEntry).where(
                    LeaderboardEntry.user_id == user_id,
                    LeaderboardEntry.board_type == board_type,
                    LeaderboardEntry.period == period,
                )
                result = await session.execute(stmt)
                entry = result.scalar_one_or_none()

                if entry:
                    entry.score = LeaderboardEntry.score + score
                else:
                    entry = LeaderboardEntry(
                        user_id=user_id,
                        board_type=board_type,
                        period=period,
                        score=score,
                    )
                    session.add(entry)

            await session.commit()

        logger.info(f"🏆 记录分数: {board_type} user={payload['user_id'][:8] if isinstance(payload.get('user_id'), str) else str(user_id)[:8]} +{score}")

        # 失效缓存
        await cache_service.invalidate(f"leaderboard:{board_type}")

        return {"status": "ok"}

    # ── 获取排行榜 ──
    @cached("leaderboard", ttl=60)
    async def get_board(self, payload: dict) -> dict:
        board_type = payload.get("board_type", "coins")
        period = payload.get("period", "daily")
        limit = payload.get("limit", 20)
        user_id = payload.get("user_id")

        async with AsyncSessionLocal() as session:
            # 查询排行榜条目
            stmt = (
                select(LeaderboardEntry)
                .where(
                    LeaderboardEntry.board_type == board_type,
                    LeaderboardEntry.period == period,
                )
                .order_by(LeaderboardEntry.score.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            entries = result.scalars().all()

            # 构建排名列表
            rank_list = []
            for rank, entry in enumerate(entries, 1):
                rank_list.append({
                    "rank": rank,
                    "user_id": str(entry.user_id),
                    "score": entry.score,
                })

            # 查询用户个人排名
            user_rank = None
            if user_id:
                uid = _uuid.UUID(user_id) if isinstance(user_id, str) else user_id

                # 总人数
                total_stmt = select(sa_func.count()).select_from(LeaderboardEntry).where(
                    LeaderboardEntry.board_type == board_type,
                    LeaderboardEntry.period == period,
                )
                total_result = await session.execute(total_stmt)
                total_count = total_result.scalar()

                # 用户条目
                user_stmt = select(LeaderboardEntry).where(
                    LeaderboardEntry.user_id == uid,
                    LeaderboardEntry.board_type == board_type,
                    LeaderboardEntry.period == period,
                )
                user_result = await session.execute(user_stmt)
                user_entry = user_result.scalar_one_or_none()

                if user_entry:
                    # 比我分高的人数
                    better_stmt = select(sa_func.count()).select_from(LeaderboardEntry).where(
                        LeaderboardEntry.board_type == board_type,
                        LeaderboardEntry.period == period,
                        LeaderboardEntry.score > user_entry.score,
                    )
                    better_result = await session.execute(better_stmt)
                    better_count = better_result.scalar()

                    user_rank = {
                        "rank": better_count + 1,
                        "score": user_entry.score,
                        "total": total_count,
                    }

        return {
            "board_type": board_type,
            "period": period,
            "entries": rank_list,
            "user_rank": user_rank,
        }

    # ── 获取个人排名 ──
    async def get_rank(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        uid = _uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        async with AsyncSessionLocal() as session:
            # 查用户所有条目
            stmt = select(LeaderboardEntry).where(LeaderboardEntry.user_id == uid)
            result = await session.execute(stmt)
            entries = result.scalars().all()

            ranks = {}
            for entry in entries:
                key = f"{entry.board_type}_{entry.period}"

                # 比我分高的人数
                better_stmt = select(sa_func.count()).select_from(LeaderboardEntry).where(
                    LeaderboardEntry.board_type == entry.board_type,
                    LeaderboardEntry.period == entry.period,
                    LeaderboardEntry.score > entry.score,
                )
                better_result = await session.execute(better_stmt)
                better = better_result.scalar()

                # 总人数
                total_stmt = select(sa_func.count()).select_from(LeaderboardEntry).where(
                    LeaderboardEntry.board_type == entry.board_type,
                    LeaderboardEntry.period == entry.period,
                )
                total_result = await session.execute(total_stmt)
                total = total_result.scalar()

                ranks[key] = {"rank": better + 1, "score": entry.score, "total": total}

            # 对于用户还没有条目的 board_type+period 组合，补齐默认值
            for board_type in self.TYPES:
                for period in ["daily", "weekly", "all"]:
                    key = f"{board_type}_{period}"
                    if key not in ranks:
                        # 查总人数（没有条目意味着 rank = total + 1）
                        total_stmt = select(sa_func.count()).select_from(LeaderboardEntry).where(
                            LeaderboardEntry.board_type == board_type,
                            LeaderboardEntry.period == period,
                        )
                        total_result = await session.execute(total_stmt)
                        total = total_result.scalar()
                        ranks[key] = {"rank": total + 1, "score": 0, "total": total}

        return {"user_id": str(uid), "ranks": ranks}

    # ── 日快照 ──
    async def daily_snapshot(self, payload: dict) -> dict:
        """生成并归档今日排行榜快照"""
        logger.info("📸 排行榜日快照")
        today = date.today()
        snapshots = {}

        async with AsyncSessionLocal() as session:
            for board_type in self.TYPES:
                stmt = (
                    select(LeaderboardEntry)
                    .where(
                        LeaderboardEntry.board_type == board_type,
                        LeaderboardEntry.period == "daily",
                    )
                    .order_by(LeaderboardEntry.score.desc())
                    .limit(10)
                )
                result = await session.execute(stmt)
                entries = result.scalars().all()

                rankings = [
                    {"rank": i + 1, "user_id": str(e.user_id), "score": e.score}
                    for i, e in enumerate(entries)
                ]
                snapshots[board_type] = rankings

                # 写入快照表（upsert: 同一天同类型覆盖）
                check_stmt = select(LeaderboardSnapshot).where(
                    LeaderboardSnapshot.period == "daily",
                    LeaderboardSnapshot.snapshot_date == today,
                    LeaderboardSnapshot.board_type == board_type,
                )
                check_result = await session.execute(check_stmt)
                existing = check_result.scalar_one_or_none()

                if existing:
                    existing.rankings = rankings
                else:
                    snapshot = LeaderboardSnapshot(
                        period="daily",
                        snapshot_date=today,
                        board_type=board_type,
                        rankings=rankings,
                    )
                    session.add(snapshot)

            await session.commit()

        return {
            "status": "ok",
            "date": today.isoformat(),
            "snapshots": snapshots,
        }
