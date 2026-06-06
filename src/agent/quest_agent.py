"""
LAWA QuestAgent — 任务系统 Agent

管理 RPG 任务生命周期：
- 可接任务列表（按等级/CEFR/技能筛选）
- 接取任务（日常/周常防重复）
- 提交任务进度
- 完成任务（发放 XP + 金币奖励，处理升级）
- 活跃任务查询
- 每日任务刷新
"""
import uuid
from datetime import datetime, date, timezone, timedelta
from typing import Optional
from loguru import logger
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.base_agent import BaseAgent
from src.database.main import AsyncSessionLocal
from src.models.quest import QuestTemplate, UserQuest, DungeonInstance
from src.models.user import User, LawaProfile
from src.services.llm_service import llm_service


# ── 升级经验表 ──
# XP needed for next level: level * 100
# Level 1 → 2: 100 XP total, Level 2 → 3: 300 XP total, etc.
def _xp_for_level(level: int) -> int:
    """累计经验需求: Σ(i*100) for i from 1 to (level-1)"""
    # level 1 needs 0 to be level 1
    # level 2 needs 100 total
    # level 3 needs 100 + 200 = 300 total
    # level n needs sum(1..n-1)*100 = (n-1)*n/2*100
    return (level - 1) * level * 50  # 50 * (n-1)*n


class QuestAgent(BaseAgent):
    """任务系统核心 Agent"""

    def __init__(self):
        super().__init__("QuestAgent")

    async def execute(self, payload: dict) -> dict:
        """
        payload:
        {
            "action": "list_available | accept | submit | complete | get_active | get_daily",
            "user_id": "...",
            ...
        }
        """
        action = payload.get("action", "get_active")
        handlers = {
            "list_available": self.list_available,
            "accept": self.accept,
            "submit": self.submit,
            "complete": self.complete,
            "get_active": self.get_active,
            "get_daily": self.get_daily,
            "generate_content": self.generate_quest_content,
            "generate_daily_quest": self.generate_daily_quest,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    # ── 数据库辅助 ──

    async def _get_profile(self, session: AsyncSession, user_id: str) -> Optional[LawaProfile]:
        """获取用户 LAWA 画像"""
        result = await session.execute(
            select(LawaProfile).where(LawaProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_quest_template(self, session: AsyncSession, quest_id: str) -> Optional[QuestTemplate]:
        """获取任务模板（by id or code）"""
        # try UUID first, then code
        try:
            uid = uuid.UUID(quest_id)
            result = await session.execute(
                select(QuestTemplate).where(QuestTemplate.id == uid)
            )
            qt = result.scalar_one_or_none()
            if qt:
                return qt
        except (ValueError, AttributeError):
            pass
        # try by code
        result = await session.execute(
            select(QuestTemplate).where(QuestTemplate.code == quest_id)
        )
        return result.scalar_one_or_none()

    # ── 可接任务列表 ──

    async def list_available(self, payload: dict) -> dict:
        """列出用户当前可接的任务模板"""
        user_id = payload["user_id"]
        quest_type = payload.get("quest_type")  # optional filter
        skill_focus = payload.get("skill_focus")  # optional filter

        async with AsyncSessionLocal() as session:
            profile = await self._get_profile(session, user_id)
            if not profile:
                return {"error": "用户画像不存在，请先完成初始化"}

            # 获取用户已接但未完成的日常任务 code（防止重复接取）
            today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
            if quest_type == "daily" or quest_type is None:
                completed_today = await session.execute(
                    select(UserQuest.quest_template_id).where(
                        and_(
                            UserQuest.user_id == user_id,
                            UserQuest.accepted_at >= today_start,
                            UserQuest.status.in_(["accepted", "in_progress", "completed"]),
                        )
                    )
                )
                # For daily quests, check which templates the user already has today
                accepted_template_ids = set()
                user_quests_today = await session.execute(
                    select(UserQuest).where(
                        and_(
                            UserQuest.user_id == user_id,
                            UserQuest.accepted_at >= today_start,
                        )
                    )
                )
                for uq in user_quests_today.scalars():
                    qt = await self._get_quest_template(session, str(uq.quest_template_id))
                    if qt and qt.quest_type == "daily":
                        accepted_template_ids.add(uq.quest_template_id)

            # 构建查询
            conditions = []
            if quest_type:
                conditions.append(QuestTemplate.quest_type == quest_type)
            if skill_focus:
                conditions.append(QuestTemplate.skill_focus == skill_focus)
            # 按用户学习语言过滤任务（zh学习者看zh-，en学习者看en-）
            user_lang = (profile.learn_lang or "en").split(",")[0].strip()
            lang_prefix = user_lang if user_lang in ("zh", "en") else "en"
            conditions.append(QuestTemplate.code.like(f"{lang_prefix}-%"))
            # CEFR 等级筛选（仅当用户有等级时）
            if profile.current_level:
                try:
                    user_level = profile.current_level.upper()
                    conditions.append(
                        or_(
                            QuestTemplate.cefr_min.is_(None),
                            func.upper(QuestTemplate.cefr_min) <= user_level,
                        )
                    )
                    conditions.append(
                        or_(
                            QuestTemplate.cefr_max.is_(None),
                            func.upper(QuestTemplate.cefr_max) >= user_level,
                        )
                    )
                except Exception:
                    pass  # skip level filter on parse error

            # 过滤已完成的主线任务（不能重复接）
            if quest_type == "main" or quest_type is None:
                completed_main = await session.execute(
                    select(UserQuest.quest_template_id).where(
                        and_(
                            UserQuest.user_id == user_id,
                            UserQuest.status == "completed",
                        )
                    )
                )
                completed_main_ids = {r[0] for r in completed_main.all()}
                # Also check pre-requisites: exclude quests whose pre_quest is not yet completed

            # 前置任务检查
            all_completed = await session.execute(
                select(UserQuest.quest_template_id).where(
                    and_(
                        UserQuest.user_id == user_id,
                        UserQuest.status == "completed",
                    )
                )
            )
            all_completed_ids = {r[0] for r in all_completed.all()}

            query = select(QuestTemplate).where(and_(*conditions)) if conditions else select(QuestTemplate)
            result = await session.execute(query)
            templates = result.scalars().all()

            available = []
            for t in templates:
                # Skip if daily and already accepted today
                if t.quest_type == "daily" and t.id in accepted_template_ids:
                    continue
                # Skip if pre-requisite not met
                if t.pre_quest_code:
                    pre_result = await session.execute(
                        select(QuestTemplate).where(QuestTemplate.code == t.pre_quest_code)
                    )
                    pre_qt = pre_result.scalar_one_or_none()
                    if pre_qt and pre_qt.id not in all_completed_ids:
                        continue

                available.append({
                    "id": str(t.id),
                    "code": t.code,
                    "name": t.name,
                    "description": t.description,
                    "quest_type": t.quest_type,
                    "difficulty": t.difficulty,
                    "skill_focus": t.skill_focus,
                    "cefr_min": t.cefr_min,
                    "cefr_max": t.cefr_max,
                    "xp_reward": t.xp_reward,
                    "coin_reward": t.coin_reward,
                    "item_reward_codes": t.item_reward_codes or [],
                    "time_limit_seconds": t.time_limit_seconds,
                    "content": t.content or {},
                })

            return {
                "available": available,
                "count": len(available),
                "user_level": profile.current_level,
                "user_id": user_id,
            }

    # ── 接取任务 ──

    async def accept(self, payload: dict) -> dict:
        """接取一个任务"""
        user_id = payload["user_id"]
        quest_identifier = payload["quest_code"] or payload.get("quest_id")

        if not quest_identifier:
            return {"error": "请提供 quest_code 或 quest_id"}

        async with AsyncSessionLocal() as session:
            profile = await self._get_profile(session, user_id)
            if not profile:
                return {"error": "用户画像不存在"}

            template = await self._get_quest_template(session, quest_identifier)
            if not template:
                return {"error": f"任务模板不存在: {quest_identifier}"}

            # 日常任务：检查今天是否已接
            if template.quest_type == "daily":
                today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
                existing = await session.execute(
                    select(UserQuest).where(
                        and_(
                            UserQuest.user_id == user_id,
                            UserQuest.quest_template_id == template.id,
                            UserQuest.accepted_at >= today_start,
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    return {"error": f"今日已接取日常任务: {template.name}"}

            # 主线任务：检查是否已完成
            if template.quest_type == "main":
                existing = await session.execute(
                    select(UserQuest).where(
                        and_(
                            UserQuest.user_id == user_id,
                            UserQuest.quest_template_id == template.id,
                            UserQuest.status == "completed",
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    return {"error": f"主线任务已完成: {template.name}"}

            # 前置任务检查
            if template.pre_quest_code:
                pre_result = await session.execute(
                    select(QuestTemplate).where(QuestTemplate.code == template.pre_quest_code)
                )
                pre_qt = pre_result.scalar_one_or_none()
                if pre_qt:
                    pre_completed = await session.execute(
                        select(UserQuest).where(
                            and_(
                                UserQuest.user_id == user_id,
                                UserQuest.quest_template_id == pre_qt.id,
                                UserQuest.status == "completed",
                            )
                        )
                    )
                    if not pre_completed.scalar_one_or_none():
                        return {"error": f"需要先完成任务: {pre_qt.name} (code={template.pre_quest_code})"}

            # CEFR 等级检查（仅当用户等级和模板等级使用同一评分体系时）
            if template.cefr_min or template.cefr_max:
                if profile.current_level:
                    user_lvl = profile.current_level.upper()
                    tpl_min = (template.cefr_min or "").upper()
                    tpl_max = (template.cefr_max or "").upper()
                    # 仅在同一评分体系下比较（CEFR vs CEFR, HSK vs HSK）
                    same_scale = (
                        (user_lvl.startswith("A") or user_lvl.startswith("B") or user_lvl.startswith("C"))
                        == (tpl_min.startswith("A") or tpl_min.startswith("B") or tpl_min.startswith("C"))
                    )
                    if same_scale and tpl_min and user_lvl < tpl_min:
                        return {"error": f"需要 {template.cefr_min} 以上等级"}
                    if same_scale and tpl_max and user_lvl > tpl_max:
                        return {"error": f"等级超过 {template.cefr_max}，请挑战更高难度任务"}

            # 计算过期时间
            expires_at = None
            if template.time_limit_seconds:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=template.time_limit_seconds)
            elif template.quest_type == "daily":
                # 日常任务当日23:59过期
                expires_at = datetime.combine(date.today(), datetime.max.time()).replace(tzinfo=timezone.utc)
            elif template.quest_type == "weekly":
                # 周常任务下周日23:59过期
                days_until_sunday = 6 - date.today().weekday()
                next_sunday = date.today() + timedelta(days=days_until_sunday)
                expires_at = datetime.combine(next_sunday, datetime.max.time()).replace(tzinfo=timezone.utc)

            # 创建 UserQuest
            user_quest = UserQuest(
                user_id=user_id,
                quest_template_id=template.id,
                status="accepted",
                progress={},
                expires_at=expires_at,
            )
            session.add(user_quest)
            await session.commit()
            await session.refresh(user_quest)

            logger.info(f"📋 任务接取: user={user_id}, quest={template.code}, type={template.quest_type}")

            return {
                "status": "ok",
                "user_quest": {
                    "id": str(user_quest.id),
                    "quest_code": template.code,
                    "quest_name": template.name,
                    "quest_type": template.quest_type,
                    "status": user_quest.status,
                    "xp_reward": template.xp_reward,
                    "coin_reward": template.coin_reward,
                    "expires_at": user_quest.expires_at.isoformat() if user_quest.expires_at else None,
                    "accepted_at": user_quest.accepted_at.isoformat() if user_quest.accepted_at else None,
                },
            }

    # ── 提交任务进度 ──

    async def submit(self, payload: dict) -> dict:
        """提交任务进度（作答/练习）"""
        user_quest_id = payload["user_quest_id"]
        user_id = payload["user_id"]
        progress_update = payload.get("progress", {})  # {"answered": 3, "correct": 2, "last_answer": "..."}

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserQuest).where(
                    and_(UserQuest.id == user_quest_id, UserQuest.user_id == user_id)
                )
            )
            user_quest = result.scalar_one_or_none()
            if not user_quest:
                return {"error": "任务不存在或不属于此用户"}

            if user_quest.status not in ("accepted", "in_progress"):
                return {"error": f"任务状态为 {user_quest.status}，无法提交进度"}

            # Mark as in_progress on first submit
            if user_quest.status == "accepted":
                user_quest.status = "in_progress"

            # Merge progress
            current_progress = user_quest.progress or {}
            current_progress.update(progress_update)
            user_quest.progress = current_progress

            await session.commit()

            logger.info(f"📤 任务进度更新: quest={user_quest_id}, progress={progress_update}")

            return {
                "status": "ok",
                "user_quest_id": str(user_quest.id),
                "quest_status": user_quest.status,
                "progress": user_quest.progress,
            }

    # ── 完成任务 ──

    async def complete(self, payload: dict) -> dict:
        """完成任务并发放奖励（XP + 金币 + 升级判断）"""
        user_quest_id = payload["user_quest_id"]
        user_id = payload["user_id"]

        async with AsyncSessionLocal() as session:
            # 获取任务实例
            result = await session.execute(
                select(UserQuest).where(
                    and_(UserQuest.id == user_quest_id, UserQuest.user_id == user_id)
                )
            )
            user_quest = result.scalar_one_or_none()
            if not user_quest:
                return {"error": "任务不存在或不属于此用户"}

            if user_quest.status == "completed":
                return {"error": "任务已完成", "already_completed": True}

            if user_quest.status not in ("accepted", "in_progress"):
                return {"error": f"任务状态为 {user_quest.status}，无法完成"}

            # 检查过期（SQLite 存储的可能不带时区）
            if user_quest.expires_at:
                now = datetime.now(timezone.utc)
                expires = user_quest.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if expires < now:
                    user_quest.status = "expired"
                    await session.commit()
                    return {"error": "任务已过期"}

            # 获取模板
            template = await self._get_quest_template(session, str(user_quest.quest_template_id))
            if not template:
                return {"error": "任务模板不存在"}

            # 获取用户画像
            profile = await self._get_profile(session, user_id)
            if not profile:
                return {"error": "用户画像不存在"}

            # 标记完成
            user_quest.status = "completed"
            user_quest.completed_at = datetime.now(timezone.utc)
            # Mark final progress as 100% complete
            template_goal = template.content.get("goal_count", 1) if template.content else 1
            current_answered = (user_quest.progress or {}).get("answered", 0)
            user_quest.progress = {
                **(user_quest.progress or {}),
                "answered": max(current_answered, template_goal),
                "completed": True,
            }

            # 发放 XP 奖励
            xp_before = profile.xp or 0
            xp_gained = template.xp_reward
            xp_after = xp_before + xp_gained

            # 升级检测
            level_before = profile.level or 1
            level_after = level_before
            while xp_after >= _xp_for_level(level_after + 1):
                level_after += 1

            profile.xp = xp_after
            profile.level = level_after
            if level_after > level_before:
                profile.talent_points = (profile.talent_points or 0) + (level_after - level_before)
                logger.info(f"🎉 升级! user={user_id}, {level_before}→{level_after}")

            # 发放金币奖励
            coin_before = profile.total_coins or 0
            coin_gained = template.coin_reward
            profile.total_coins = coin_before + coin_gained

            await session.commit()

            logger.info(
                f"✅ 任务完成: user={user_id}, quest={template.code}, "
                f"+{xp_gained}XP, +{coin_gained}🪙, Lv{level_before}→Lv{level_after}"
            )

            return {
                "status": "ok",
                "user_quest_id": str(user_quest.id),
                "quest_code": template.code,
                "quest_name": template.name,
                "completed_at": user_quest.completed_at.isoformat(),
                "rewards": {
                    "xp_gained": xp_gained,
                    "xp_total": xp_after,
                    "coin_gained": coin_gained,
                    "coin_total": profile.total_coins,
                    "level_before": level_before,
                    "level_after": level_after,
                    "talent_points_gained": level_after - level_before,
                    "talent_points_total": profile.talent_points or 0,
                    "xp_to_next_level": _xp_for_level(level_after + 1) - xp_after if level_after < 99 else 0,
                },
            }

    # ── 活跃任务查询 ──

    async def get_active(self, payload: dict) -> dict:
        """获取用户当前活跃任务"""
        user_id = payload["user_id"]

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserQuest).where(
                    and_(
                        UserQuest.user_id == user_id,
                        UserQuest.status.in_(["accepted", "in_progress"]),
                    )
                ).order_by(UserQuest.accepted_at.desc())
            )
            active_quests = result.scalars().all()

            quests_data = []
            for uq in active_quests:
                template = await self._get_quest_template(session, str(uq.quest_template_id))
                quests_data.append({
                    "id": str(uq.id),
                    "quest_code": template.code if template else "unknown",
                    "quest_name": template.name if template else "未知任务",
                    "quest_type": template.quest_type if template else "unknown",
                    "status": uq.status,
                    "progress": uq.progress or {},
                    "xp_reward": template.xp_reward if template else 0,
                    "coin_reward": template.coin_reward if template else 0,
                    "expires_at": uq.expires_at.isoformat() if uq.expires_at else None,
                    "accepted_at": uq.accepted_at.isoformat() if uq.accepted_at else None,
                })

            return {
                "active_quests": quests_data,
                "count": len(quests_data),
                "user_id": user_id,
            }

    # ── 每日任务 ──

    async def get_daily(self, payload: dict) -> dict:
        """获取今日可接的日常任务 + 用户当前日常进度"""
        user_id = payload["user_id"]

        async with AsyncSessionLocal() as session:
            profile = await self._get_profile(session, user_id)
            if not profile:
                return {"error": "用户画像不存在"}

            # 今日已接日常
            today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
            result = await session.execute(
                select(UserQuest).where(
                    and_(
                        UserQuest.user_id == user_id,
                        UserQuest.accepted_at >= today_start,
                    )
                )
            )
            today_quests = result.scalars().all()

            # Build today's status
            today_data = []
            for uq in today_quests:
                template = await self._get_quest_template(session, str(uq.quest_template_id))
                if template and template.quest_type == "daily":
                    today_data.append({
                        "user_quest_id": str(uq.id),
                        "quest_code": template.code,
                        "quest_name": template.name,
                        "status": uq.status,
                        "progress": uq.progress or {},
                        "xp_reward": template.xp_reward,
                        "coin_reward": template.coin_reward,
                        "accepted_at": uq.accepted_at.isoformat() if uq.accepted_at else None,
                        "completed_at": uq.completed_at.isoformat() if uq.completed_at else None,
                    })

            # All available daily quests
            result = await session.execute(
                select(QuestTemplate).where(QuestTemplate.quest_type == "daily")
            )
            all_dailies = result.scalars().all()

            # Add unclaimed dailies
            accepted_codes = {d["quest_code"] for d in today_data}
            for t in all_dailies:
                if t.code not in accepted_codes:
                    today_data.append({
                        "user_quest_id": None,
                        "quest_code": t.code,
                        "quest_name": t.name,
                        "status": "available",
                        "progress": {},
                        "xp_reward": t.xp_reward,
                        "coin_reward": t.coin_reward,
                        "accepted_at": None,
                        "completed_at": None,
                    })

            completed_count = sum(1 for d in today_data if d["status"] == "completed")
            total_count = len(today_data)

            return {
                "daily_quests": today_data,
                "total": total_count,
                "completed": completed_count,
                "date": date.today().isoformat(),
                "user_id": user_id,
            }

    # ── LLM 驱动：任务内容动态生成 ──

    async def generate_quest_content(self, payload: dict) -> dict:
        """由 LLM 为任务生成具体内容（题目/对话/阅读材料/文化注解）

        payload: {
            "quest_code": "existing quest code to fill content",
            "lang": "en" | "zh",
            "skill_focus": "grammar" | "vocabulary" | "reading" | "writing" | "speaking",
            "user_level": "B1" | "HSK3",
            "quest_type": "daily" | "weekly" | "main"
        }
        """
        lang = payload.get("lang", "en")
        skill_focus = payload.get("skill_focus", "vocabulary")
        user_level = payload.get("user_level", "B1" if lang == "en" else "HSK3")
        quest_type = payload.get("quest_type", "daily")
        quest_code = payload.get("quest_code")

        # 如果指定了已有任务 code，获取其基本信息
        quest_context = ""
        if quest_code:
            async with AsyncSessionLocal() as session:
                template = await self._get_quest_template(session, quest_code)
                if template:
                    quest_context = f"Quest name: {template.name}\nDescription: {template.description}\n"

        lang_name = "English" if lang == "en" else "中文"
        goal_count = 5 if quest_type == "daily" else 10

        system_prompt = f"""You are a creative language teaching content designer.
Generate engaging quest content for a {lang_name} learner at level {user_level}.

Quest type: {quest_type}
Skill focus: {skill_focus}
Number of questions: {goal_count}
{quest_context}

Based on the skill focus, generate appropriate content:
- grammar: sentences with fill-in-the-blank, error correction, or multiple choice
- vocabulary: words with definitions, usage examples, or matching
- reading: a short passage (100-200 words) with comprehension questions
- writing: a creative writing prompt with guidance
- speaking: dialogue prompts or pronunciation challenges

Return JSON:
{{
  "instructions": "Clear task instructions for the learner",
  "questions": [
    {{
      "id": 1,
      "type": "fill_blank" | "multiple_choice" | "short_answer" | "open_ended",
      "prompt": "The question text",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "The correct answer",
      "hint": "Optional hint"
    }}
  ],
  "passage": "Reading passage text (only for reading skill)",
  "cultural_note": "A fun cultural tidbit related to the content",
  "learning_tip": "A helpful learning strategy tip"
}}

Make it fun and culturally authentic. Use real-world contexts."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate {goal_count} {skill_focus} questions for {quest_type} quest at {user_level} level."},
        ]

        content = await llm_service.chat_json(
            messages=messages,
            task="simple",
            temperature=0.8,
        )

        # 如果指定了 quest_code，保存到 DB
        if quest_code and "error" not in content:
            async with AsyncSessionLocal() as session:
                template = await self._get_quest_template(session, quest_code)
                if template:
                    template.content = {
                        **(template.content or {}),
                        "llm_generated": content,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "generated_for_level": user_level,
                    }
                    await session.commit()
                    logger.info(f"📝 Quest content saved: {quest_code} | {skill_focus} | {user_level}")

        return {
            "content": content,
            "quest_code": quest_code,
            "skill_focus": skill_focus,
            "user_level": user_level,
            "quest_type": quest_type,
            "saved": quest_code is not None and "error" not in content,
        }

    async def generate_daily_quest(self, payload: dict) -> dict:
        """由 LLM 生成一个完整的每日任务（名称+描述+内容），写入 DB

        payload: {
            "lang": "en" | "zh",
            "skill_focus": "grammar" | "vocabulary" | "reading" | "writing" | "speaking",
            "user_level": "B1" | "HSK3"
        }
        """
        lang = payload.get("lang", "en")
        skill_focus = payload.get("skill_focus", "vocabulary")
        user_level = payload.get("user_level", "B1" if lang == "en" else "HSK3")

        lang_name = "English" if lang == "en" else "中文"
        lang_prefix = "en" if lang == "en" else "zh"

        # 先让 LLM 生成任务元信息
        meta_prompt = f"""Design a daily quest for {lang_name} learners at {user_level} level.
Skill focus: {skill_focus}

Generate a fun, original quest. Return JSON:
{{
  "code": "{lang_prefix}-daily-<creative_slug>",
  "name": "Catchy quest name with emoji",
  "description": "Engaging 1-2 sentence description",
  "difficulty": 1-10,
  "xp_reward": 20-50,
  "coin_reward": 5-15
}}

Make the code unique and descriptive."""

        meta = await llm_service.chat_json(
            messages=[
                {"role": "system", "content": meta_prompt},
                {"role": "user", "content": f"Create a {skill_focus} daily quest for {user_level}."},
            ],
            task="simple",
            temperature=0.9,
        )

        # 生成具体内容
        content = await self.generate_quest_content({
            "lang": lang,
            "skill_focus": skill_focus,
            "user_level": user_level,
            "quest_type": "daily",
        })

        if "error" in content.get("content", {}):
            return {"error": "内容生成失败", "meta": meta}

        # 写入 DB
        async with AsyncSessionLocal() as session:
            # 检查 code 是否已存在
            from sqlalchemy import select as sa_select
            code = meta.get("code", f"{lang_prefix}-daily-{skill_focus}-{uuid.uuid4().hex[:6]}")
            existing = await session.execute(
                sa_select(QuestTemplate).where(QuestTemplate.code == code)
            )
            if existing.scalar_one_or_none():
                code = f"{code}-{uuid.uuid4().hex[:4]}"

            template = QuestTemplate(
                code=code,
                name=meta.get("name", f"Daily {skill_focus.title()}"),
                description=meta.get("description", ""),
                quest_type="daily",
                difficulty=meta.get("difficulty", 3),
                skill_focus=skill_focus,
                cefr_min=user_level if lang == "en" else None,
                cefr_max=user_level if lang == "en" else None,
                xp_reward=meta.get("xp_reward", 25),
                coin_reward=meta.get("coin_reward", 5),
                content={
                    "llm_generated": content["content"],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "generated_for_level": user_level,
                },
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)

            logger.info(f"🆕 每日任务已生成: {code} | {skill_focus} | Lv{user_level}")

            return {
                "quest": {
                    "id": str(template.id),
                    "code": template.code,
                    "name": template.name,
                    "description": template.description,
                    "quest_type": template.quest_type,
                    "skill_focus": template.skill_focus,
                    "difficulty": template.difficulty,
                    "xp_reward": template.xp_reward,
                    "coin_reward": template.coin_reward,
                    "content": template.content,
                },
                "generated": True,
            }
