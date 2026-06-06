"""
GuildAgent —— 公会系统核心

管理：创建/加入/退出公会、贡献、公会任务、升级
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select, and_, func, update
from src.database import AsyncSessionLocal
from src.database.session import get_async_session
from src.models.guild import LanguageGuild, GuildMember, GuildTask, get_guild_level_config
from src.models.user import LawaProfile
from src.models.quest import QuestTemplate
from src.agent.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class GuildAgent(BaseAgent):
    """公会 Agent"""

    def __init__(self):
        super().__init__(name="GuildAgent")

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "")
        handlers = {
            "list": self.list_guilds,
            "my_guild": self.my_guild,
            "create": self.create_guild,
            "join": self.join_guild,
            "leave": self.leave_guild,
            "detail": self.guild_detail,
            "contribute": self.contribute,
            "tasks": self.guild_tasks,
            "task_progress": self.task_progress,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        try:
            result = await handler(payload)
            self.log_execution(payload, result)
            return result
        except Exception as e:
            logger.error(f"GuildAgent error: {e}")
            return {"error": str(e)}

    # ── 公会列表 ──

    async def list_guilds(self, payload: dict) -> dict:
        language = payload.get("language", "en")
        async with get_async_session() as session:
            query = select(LanguageGuild).where(LanguageGuild.language == language)
            if payload.get("name"):
                query = query.where(LanguageGuild.name.ilike(f"%{payload['name']}%"))
            query = query.order_by(LanguageGuild.level.desc(), LanguageGuild.member_count.desc())
            result = await session.execute(query)
            guilds = result.scalars().all()
            return {
                "guilds": [
                    {
                        "id": str(g.id),
                        "name": g.name,
                        "emblem": g.emblem,
                        "description": g.description,
                        "level": g.level,
                        "member_count": g.member_count,
                        "member_limit": g.member_limit,
                        "buffs": g.buffs,
                    }
                    for g in guilds
                ],
                "count": len(guilds),
            }

    # ── 我的公会 ──

    async def my_guild(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        async with get_async_session() as session:
            m_result = await session.execute(
                select(GuildMember).where(GuildMember.user_id == user_id)
            )
            memberships = m_result.scalars().all()
            if not memberships:
                return {"in_guild": False}

            # 返回主公会（role=owner 优先，否则第一个）
            primary = next((m for m in memberships if m.role == "owner"), memberships[0])
            g_result = await session.execute(
                select(LanguageGuild).where(LanguageGuild.id == primary.guild_id)
            )
            guild = g_result.scalar_one_or_none()
            if not guild:
                return {"in_guild": False}

            result = await self._guild_detail_dict(session, guild, primary)
            result["other_guilds"] = [
                str(m.guild_id) for m in memberships if str(m.guild_id) != str(primary.guild_id)
            ]
            return result

    # ── 创建公会 ──

    async def create_guild(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        name = payload["name"]
        language = payload.get("language", "en")
        description = payload.get("description", "")
        emblem = payload.get("emblem", "🛡️")

        async with get_async_session() as session:
            # 检查用户是否已在公会（允许加入多个公会，只需不在目标公会中）
            existing = await session.execute(
                select(GuildMember).where(GuildMember.user_id == user_id)
            )
            memberships = existing.scalars().all()
            # 用户可以在多个公会，但不允许重复创建（owner角色只允许一个）
            if any(m.role == "owner" for m in memberships):
                return {"error": "你已经拥有一个公会，请先解散或转让"}
            # 限制最多3个公会
            if len(memberships) >= 3:
                return {"error": "你已经加入了3个公会，请先退出某个"}

            # 检查名称唯一性
            dup = await session.execute(
                select(LanguageGuild).where(LanguageGuild.name == name)
            )
            if dup.scalar_one_or_none():
                return {"error": "公会名已存在"}

            guild = LanguageGuild(
                name=name,
                description=description,
                language=language,
                emblem=emblem,
                owner_id=user_id,
            )
            session.add(guild)
            await session.flush()

            member = GuildMember(
                guild_id=guild.id,
                user_id=user_id,
                role="owner",
            )
            session.add(member)
            guild.member_count = 1
            await session.commit()
            await session.refresh(guild)

            logger.info(f"🏛️ 公会创建: {name} (owner={user_id})")
            return {
                "status": "ok",
                "guild": {
                    "id": str(guild.id),
                    "name": guild.name,
                    "emblem": guild.emblem,
                    "level": guild.level,
                    "member_count": 1,
                    "member_limit": guild.member_limit,
                }
            }

    # ── 加入公会 ──

    async def join_guild(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        guild_id = payload["guild_id"]

        async with get_async_session() as session:
            # 检查是否已在目标公会中
            existing = await session.execute(
                select(GuildMember).where(
                    and_(GuildMember.user_id == user_id, GuildMember.guild_id == guild_id)
                )
            )
            if existing.scalar_one_or_none():
                return {"error": "你已在此公会中"}

            # 限制最多3个公会
            all_memberships = await session.execute(
                select(GuildMember).where(GuildMember.user_id == user_id)
            )
            if len(all_memberships.scalars().all()) >= 3:
                return {"error": "你已经加入了3个公会，请先退出某个"}

            guild = await session.get(LanguageGuild, guild_id)
            if not guild:
                return {"error": "公会不存在"}

            if guild.member_count >= guild.member_limit:
                return {"error": f"公会已满员 ({guild.member_count}/{guild.member_limit})"}

            member = GuildMember(guild_id=guild_id, user_id=user_id)
            session.add(member)
            guild.member_count = guild.member_count + 1
            await session.commit()

            logger.info(f"👤 加入公会: user={user_id}, guild={guild.name}")
            return {"status": "ok", "guild_name": guild.name}

    # ── 退出公会 ──

    async def leave_guild(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        guild_id = payload.get("guild_id")  # 可选：指定退出哪个
        async with get_async_session() as session:
            member_result = await session.execute(
                select(GuildMember).where(GuildMember.user_id == user_id)
            )
            members = member_result.scalars().all()
            if not members:
                return {"error": "你未加入任何公会"}
            # 指定guild_id则退出指定公会，否则退出第一个
            if guild_id:
                member = next((m for m in members if str(m.guild_id) == guild_id), None)
                if not member:
                    return {"error": "你不在该公会中"}
            else:
                member = members[0]

            guild = await session.get(LanguageGuild, member.guild_id)
            if guild and guild.owner_id == user_id:
                return {"error": "会长不能直接退出，请先转让会长"}

            await session.delete(member)
            if guild:
                guild.member_count = max(0, guild.member_count - 1)
            await session.commit()

            return {"status": "ok", "message": "已退出公会"}

    # ── 公会详情 ──

    async def guild_detail(self, payload: dict) -> dict:
        guild_id = payload["guild_id"]
        async with get_async_session() as session:
            guild = await session.get(LanguageGuild, guild_id)
            if not guild:
                return {"error": "公会不存在"}

            return await self._guild_detail_dict(session, guild)

    # ── 贡献 ──

    async def contribute(self, payload: dict) -> dict:
        """成员贡献"""
        user_id = payload["user_id"]
        amount = payload.get("amount", 10)
        source = payload.get("source", "study")

        async with get_async_session() as session:
            member_result = await session.execute(
                select(GuildMember).where(GuildMember.user_id == user_id)
            )
            members = member_result.scalars().all()
            if not members:
                return {"error": "你未加入任何公会"}
            # 优先主公会（owner），否则第一个
            member = next((m for m in members if m.role == "owner"), members[0])

            guild = await session.get(LanguageGuild, member.guild_id)
            if not guild:
                return {"error": "公会不存在"}

            # 更新贡献值
            member.contribution = (member.contribution or 0) + amount
            guild.xp = (guild.xp or 0) + amount

            # 检查公会升级
            leveled_up = False
            old_level = guild.level
            cfg = get_guild_level_config(guild.level + 1)
            if guild.xp >= cfg["xp_required"]:
                guild.level += 1
                guild.member_limit = cfg["member_limit"]
                guild.buffs = guild.buffs or {}
                guild.buffs["xp_bonus_pct"] = cfg["buff_bonus_pct"]
                leveled_up = True

            await session.commit()

            return {
                "status": "ok",
                "contribution_added": amount,
                "member_contribution": member.contribution,
                "guild_xp": guild.xp,
                "guild_level": guild.level,
                "leveled_up": leveled_up,
                "old_level": old_level if leveled_up else None,
            }

    # ── 公会任务 ──

    async def guild_tasks(self, payload: dict) -> dict:
        guild_id = payload["guild_id"]
        async with get_async_session() as session:
            result = await session.execute(
                select(GuildTask).where(
                    and_(GuildTask.guild_id == guild_id, GuildTask.status == "active")
                ).order_by(GuildTask.created_at.desc())
            )
            tasks = result.scalars().all()
            return {
                "tasks": [
                    {
                        "id": str(t.id),
                        "name": t.name,
                        "description": t.description,
                        "target_value": t.target_value,
                        "current_value": t.current_value,
                        "progress_pct": round(t.current_value / max(1, t.target_value) * 100, 1),
                        "xp_reward": t.xp_reward,
                        "coin_reward": t.coin_reward,
                        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                    }
                    for t in tasks
                ],
                "count": len(tasks),
            }

    # ── 任务进度 ──

    async def task_progress(self, payload: dict) -> dict:
        guild_id = payload["guild_id"]
        task_id = payload["task_id"]
        value = payload.get("value", 1)

        async with get_async_session() as session:
            task = await session.get(GuildTask, task_id)
            if not task or str(task.guild_id) != guild_id:
                return {"error": "公会任务不存在"}

            if task.status != "active":
                return {"error": "任务已结束"}

            task.current_value = min(task.target_value, (task.current_value or 0) + value)
            completed = False
            if task.current_value >= task.target_value:
                task.status = "completed"
                guild = await session.get(LanguageGuild, task.guild_id)
                if guild:
                    guild.xp = (guild.xp or 0) + task.xp_reward
                completed = True

            await session.commit()

            return {
                "status": "ok",
                "task_completed": completed,
                "current_value": task.current_value,
                "target_value": task.target_value,
                "progress_pct": round(task.current_value / max(1, task.target_value) * 100, 1),
            }

    # ── helpers ──

    async def _guild_detail_dict(self, session, guild, my_member=None) -> dict:
        members_result = await session.execute(
            select(GuildMember).where(GuildMember.guild_id == guild.id)
            .order_by(GuildMember.contribution.desc())
        )
        members = members_result.scalars().all()

        tasks_result = await session.execute(
            select(GuildTask).where(
                and_(GuildTask.guild_id == guild.id, GuildTask.status == "active")
            )
        )
        active_tasks = len(tasks_result.scalars().all())

        return {
            "guild": {
                "id": str(guild.id),
                "name": guild.name,
                "emblem": guild.emblem,
                "description": guild.description,
                "level": guild.level,
                "xp": guild.xp,
                "member_count": guild.member_count,
                "member_limit": guild.member_limit,
                "buffs": guild.buffs,
                "active_tasks": active_tasks,
            },
            "members": [
                {
                    "user_id": m.user_id,
                    "role": m.role,
                    "contribution": m.contribution,
                    "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                }
                for m in members
            ],
            "my_role": my_member.role if my_member else None,
        }
