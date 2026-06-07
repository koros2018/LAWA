"""
EventAgent —— 文化节日 & 限时活动

管理：活动列表/参与/任务进度/奖励领取
"""
import uuid
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, and_
from src.database import AsyncSessionLocal

from src.models.event import CulturalEvent, UserEvent, SEED_EVENTS
from src.agent.base_agent import BaseAgent
from src.services.llm_service import llm_service

logger = logging.getLogger(__name__)
class EventAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="EventAgent")

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "list")
        handlers = {
            "list": self.list_events,
            "detail": self.event_detail,
            "join": self.join_event,
            "progress": self.submit_progress,
            "my": self.my_events,
            "generate_event": self.generate_event,
            "generate_event_content": self.generate_event_content,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        try:
            result = await handler(payload)
            self.log_execution(payload, result)
            return result
        except Exception as e:
            logger.error(f"EventAgent error: {e}")
            return {"error": str(e)}

    # ── 活动列表 ──

    async def list_events(self, payload: dict) -> dict:
        event_type = payload.get("event_type", "all")
        zone_code = payload.get("zone_code")
        user_id = payload.get("user_id")

        async with AsyncSessionLocal() as session:
            await self._seed_events(session)

            query = select(CulturalEvent).where(CulturalEvent.is_active == True)
            if event_type != "all":
                query = query.where(CulturalEvent.event_type == event_type)
            if zone_code:
                query = query.where(CulturalEvent.zone_code == zone_code)
            query = query.order_by(CulturalEvent.sort_order, CulturalEvent.created_at)

            result = await session.execute(query)
            events = result.scalars().all()

            # 获取用户参与状态
            user_events = {}
            if user_id:
                ue_result = await session.execute(
                    select(UserEvent).where(UserEvent.user_id == user_id)
                )
                for ue in ue_result.scalars().all():
                    user_events[str(ue.event_id)] = ue

            items = []
            for e in events:
                # 检查时间有效性
                now = datetime.now(timezone.utc)
                is_expired = False
                if e.end_date and e.end_date < now:
                    is_expired = True
                not_started = False
                if e.start_date and e.start_date > now:
                    not_started = True

                ue = user_events.get(str(e.id))

                items.append({
                    "id": str(e.id),
                    "code": e.code,
                    "name": e.name,
                    "emoji": e.emoji,
                    "description": e.description,
                    "event_type": e.event_type,
                    "zone_code": e.zone_code,
                    "start_date": e.start_date.isoformat() if e.start_date else None,
                    "end_date": e.end_date.isoformat() if e.end_date else None,
                    "requirement_level": e.requirement_level,
                    "tasks": e.tasks,
                    "task_count": len(e.tasks) if e.tasks else 0,
                    "rewards": e.rewards,
                    "is_expired": is_expired,
                    "not_started": not_started,
                    "joined": ue is not None,
                    "completed": bool(ue.completed) if ue else False,
                    "completed_tasks": ue.completed_tasks if ue else [],
                })

            return {
                "events": items,
                "count": len(items),
                "types": sorted(set(e["event_type"] for e in items)),
            }

    # ── 活动详情 ──

    async def event_detail(self, payload: dict) -> dict:
        event_code = payload.get("code")
        user_id = payload.get("user_id")

        async with AsyncSessionLocal() as session:
            await self._seed_events(session)

            result = await session.execute(
                select(CulturalEvent).where(CulturalEvent.code == event_code)
            )
            event = result.scalar_one_or_none()
            if not event:
                return {"error": f"活动不存在: {event_code}"}

            # 用户状态
            ue = None
            if user_id:
                ue_result = await session.execute(
                    select(UserEvent).where(
                        and_(UserEvent.user_id == user_id, UserEvent.event_id == event.id)
                    )
                )
                ue = ue_result.scalar_one_or_none()

            return {
                "id": str(event.id),
                "code": event.code,
                "name": event.name,
                "emoji": event.emoji,
                "description": event.description,
                "event_type": event.event_type,
                "zone_code": event.zone_code,
                "start_date": event.start_date.isoformat() if event.start_date else None,
                "end_date": event.end_date.isoformat() if event.end_date else None,
                "requirement_level": event.requirement_level,
                "requirement_quest": event.requirement_quest,
                "tasks": event.tasks,
                "rewards": event.rewards,
                "joined": ue is not None,
                "progress": {
                    "task_index": ue.task_index if ue else 0,
                    "task_progress": ue.task_progress if ue else 0,
                    "completed_tasks": ue.completed_tasks if ue else [],
                    "completed": bool(ue.completed) if ue else False,
                } if ue else None,
            }

    # ── 参与活动 ──

    async def join_event(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        event_code = payload["code"]

        async with AsyncSessionLocal() as session:
            await self._seed_events(session)

            # 找活动
            event_result = await session.execute(
                select(CulturalEvent).where(CulturalEvent.code == event_code)
            )
            event = event_result.scalar_one_or_none()
            if not event:
                return {"error": f"活动不存在: {event_code}"}
            if not event.is_active:
                return {"error": "活动已关闭"}

            # 检查是否已参与
            existing = await session.execute(
                select(UserEvent).where(
                    and_(UserEvent.user_id == user_id, UserEvent.event_id == event.id)
                )
            )
            if existing.scalar_one_or_none():
                return {"error": "已参与该活动"}

            # 检查时间
            now = datetime.now(timezone.utc)
            if event.start_date and event.start_date > now:
                return {"error": "活动尚未开始"}
            if event.end_date and event.end_date < now:
                return {"error": "活动已结束"}

            # 检查等级
            if event.requirement_level > 1:
                from src.models.user import LawaProfile
                profile_result = await session.execute(
                    select(LawaProfile).where(LawaProfile.user_id == user_id)
                )
                profile = profile_result.scalar_one_or_none()
                if not profile or (profile.level or 0) < event.requirement_level:
                    return {"error": f"需要等级 {event.requirement_level}"}

            # 创建参与记录
            ue = UserEvent(
                user_id=user_id,
                event_id=event.id,
                task_index=0,
                task_progress=0,
            )
            session.add(ue)
            await session.commit()

            return {
                "joined": True,
                "event_code": event_code,
                "event_name": event.name,
                "tasks": event.tasks,
                "message": f"🎉 成功参与「{event.name}」！共 {len(event.tasks)} 个任务等你完成。",
            }

    # ── 提交进度 ──

    async def submit_progress(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        event_code = payload["code"]
        task_index = payload.get("task_index")  # 指定任务序号
        progress_value = payload.get("value", 1)

        async with AsyncSessionLocal() as session:
            # 找活动
            event_result = await session.execute(
                select(CulturalEvent).where(CulturalEvent.code == event_code)
            )
            event = event_result.scalar_one_or_none()
            if not event:
                return {"error": f"活动不存在: {event_code}"}

            # 找参与记录
            ue_result = await session.execute(
                select(UserEvent).where(
                    and_(UserEvent.user_id == user_id, UserEvent.event_id == event.id)
                )
            )
            ue = ue_result.scalar_one_or_none()
            if not ue:
                return {"error": "尚未参与该活动，请先 join"}
            if ue.completed:
                return {"error": "活动已完成"}

            # 确定任务
            tasks = event.tasks or []
            if task_index is not None and 0 <= task_index < len(tasks):
                current_idx = task_index
            else:
                current_idx = ue.task_index

            if current_idx >= len(tasks):
                return {"error": "所有任务已完成"}

            task = tasks[current_idx]
            ue.task_progress += progress_value

            result_msg = {
                "event_code": event_code,
                "task_index": current_idx,
                "task_desc": task["desc"],
                "progress": ue.task_progress,
                "target": task["target"],
            }

            # 当前任务完成
            if ue.task_progress >= task["target"]:
                completed_list = list(ue.completed_tasks or [])
                completed_list.append(current_idx)
                ue.completed_tasks = completed_list
                ue.task_index = current_idx + 1
                ue.task_progress = 0

                result_msg["task_completed"] = True
                result_msg["xp_earned"] = task.get("xp", 0)
                result_msg["coins_earned"] = task.get("coins", 0)

                # 发放即时奖励
                if task.get("xp") or task.get("coins"):
                    from src.models.user import LawaProfile
                    profile_result = await session.execute(
                        select(LawaProfile).where(LawaProfile.user_id == user_id)
                    )
                    profile = profile_result.scalar_one_or_none()
                    if profile:
                        if task.get("xp"):
                            profile.xp = (profile.xp or 0) + task["xp"]
                        if task.get("coins"):
                            profile.total_coins = (profile.total_coins or 0) + task["coins"]

                # 全部任务完成
                if current_idx + 1 >= len(tasks):
                    ue.completed = True
                    ue.completed_at = datetime.now(timezone.utc)
                    result_msg["event_completed"] = True
                    result_msg["final_rewards"] = event.rewards

                    # 发放最终奖励
                    rewards = event.rewards or {}
                    if rewards.get("xp") or rewards.get("coins"):
                        from src.models.user import LawaProfile
                        profile_result = await session.execute(
                            select(LawaProfile).where(LawaProfile.user_id == user_id)
                        )
                        profile = profile_result.scalar_one_or_none()
                        if profile:
                            if rewards.get("xp"):
                                profile.xp = (profile.xp or 0) + rewards["xp"]
                            if rewards.get("coins"):
                                profile.total_coins = (profile.total_coins or 0) + rewards["coins"]

            await session.commit()
            return result_msg

    # ── 我的活动 ──

    async def my_events(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        async with AsyncSessionLocal() as session:
            ue_result = await session.execute(
                select(UserEvent).where(UserEvent.user_id == user_id)
            )
            user_events = ue_result.scalars().all()

            items = []
            for ue in user_events:
                event_result = await session.execute(
                    select(CulturalEvent).where(CulturalEvent.id == ue.event_id)
                )
                event = event_result.scalar_one_or_none()
                if not event:
                    continue

                tasks = event.tasks or []
                items.append({
                    "event_code": event.code,
                    "event_name": event.name,
                    "emoji": event.emoji,
                    "event_type": event.event_type,
                    "task_index": ue.task_index,
                    "task_progress": ue.task_progress,
                    "completed_tasks": ue.completed_tasks or [],
                    "total_tasks": len(tasks),
                    "completed": bool(ue.completed),
                    "completed_at": ue.completed_at.isoformat() if ue.completed_at else None,
                    "progress_pct": round(
                        len(ue.completed_tasks or []) / max(len(tasks), 1) * 100, 1
                    ),
                    "rewards": event.rewards,
                })

            return {
                "events": items,
                "count": len(items),
                "completed": sum(1 for i in items if i["completed"]),
                "in_progress": sum(1 for i in items if not i["completed"]),
            }

    # ── helpers ──

    async def _seed_events(self, session) -> None:
        existing = await session.execute(select(CulturalEvent).limit(1))
        if existing.scalar_one_or_none():
            return
        for e in SEED_EVENTS:
            session.add(CulturalEvent(**e))
        await session.commit()

    # ── LLM 驱动：活动内容动态生成 ──

    async def generate_event(self, payload: dict) -> dict:
        """由 LLM 生成一个完整的文化活动（名称+描述+任务+奖励），写入 DB

        payload: {
            "lang": "en" | "zh",
            "event_type": "festival" | "limited_dungeon" | "challenge",
            "user_level": "B1" | "HSK3",
            "zone_code": "cn" | "en"
        }
        """
        lang = payload.get("lang", "en")
        event_type = payload.get("event_type", "festival")
        user_level = payload.get("user_level", "B1" if lang == "en" else "HSK3")
        zone_code = payload.get("zone_code", "en" if lang == "en" else "cn")

        lang_name = "English" if lang == "en" else "中文"
        task_count = 4 if event_type == "festival" else 3

        event_prompt = f"""Design a cultural language learning event for {lang_name} learners at {user_level} level.

Event type: {event_type}
Zone: {zone_code}

Create an original, culturally authentic event with {task_count} progressive tasks.

Return JSON:
{{
  "code": "<unique_event_code>",
  "name": "Catchy event name with emoji",
  "description": "Engaging 2-3 sentence description of the event theme",
  "tasks": [
    {{
      "desc": "Task description",
      "type": "translation" | "quiz" | "writing" | "speaking" | "reading",
      "target": 1-5,
      "xp": 10-30,
      "coins": 3-10
    }}
  ],
  "rewards": {{
    "xp": 50-150,
    "coins": 20-50,
    "item": "Item name if any"
  }},
  "requirement_level": 1-10
}}

Make it fun, educational, and culturally rich. Draw from real cultural traditions."""

        event_data = await llm_service.chat_json(
            messages=[
                {"role": "system", "content": event_prompt},
                {"role": "user", "content": f"Create a {event_type} event for {lang_name} zone {zone_code}."},
            ],
            task="simple",
            temperature=0.9,
        )

        if "error" in event_data:
            return {"error": "活动生成失败", "raw": event_data}

        # 写入 DB
        async with AsyncSessionLocal() as session:
            event = CulturalEvent(
                code=event_data.get("code", f"gen-{uuid.uuid4().hex[:8]}"),
                name=event_data.get("name", "Generated Event"),
                emoji="🎭",
                description=event_data.get("description", ""),
                event_type=event_type,
                zone_code=zone_code,
                requirement_level=event_data.get("requirement_level", 1),
                tasks=event_data.get("tasks", []),
                rewards=event_data.get("rewards", {}),
                is_active=True,
                sort_order=99,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

            logger.info(f"🎉 活动已生成: {event.code} | {event_type} | zone={zone_code}")

            return {
                "event": {
                    "id": str(event.id),
                    "code": event.code,
                    "name": event.name,
                    "description": event.description,
                    "event_type": event.event_type,
                    "zone_code": event.zone_code,
                    "requirement_level": event.requirement_level,
                    "tasks": event.tasks,
                    "task_count": len(event.tasks) if event.tasks else 0,
                    "rewards": event.rewards,
                    "is_active": event.is_active,
                },
                "generated": True,
            }

    async def generate_event_content(self, payload: dict) -> dict:
        """由 LLM 为已有活动生成/增强任务内容

        payload: {
            "event_code": "existing event code",
            "lang": "en" | "zh",
            "user_level": "B1" | "HSK3"
        }
        """
        event_code = payload.get("event_code")
        lang = payload.get("lang", "en")
        user_level = payload.get("user_level", "B1" if lang == "en" else "HSK3")

        if not event_code:
            return {"error": "event_code required"}

        lang_name = "English" if lang == "en" else "中文"

        async with AsyncSessionLocal() as session:
            await self._seed_events(session)
            result = await session.execute(
                select(CulturalEvent).where(CulturalEvent.code == event_code)
            )
            event = result.scalar_one_or_none()
            if not event:
                return {"error": f"活动不存在: {event_code}"}

            tasks = event.tasks or []
            if not tasks:
                return {"error": "活动没有任务定义"}

            # 为每个任务生成详细内容
            enriched_tasks = []
            for i, task in enumerate(tasks):
                task_prompt = f"""For a {lang_name} cultural event "{event.name}", enrich this task:

Task: {task.get('desc', 'Task ' + str(i+1))}
Type: {task.get('type', 'quiz')}
Level: {user_level}

Generate detailed task content. Return JSON:
{{
  "instructions": "Detailed task instructions (2-3 sentences)",
  "questions": [
    {{
      "q": "Question text",
      "a": "Answer text",
      "hint": "Optional hint"
    }}
  ],
  "cultural_note": "A fun cultural fact related to this task",
  "encouragement": "Motivational message on completion"
}}"""

                try:
                    detail = await llm_service.chat_json(
                        messages=[
                            {"role": "system", "content": task_prompt},
                            {"role": "user", "content": f"Enrich task {i+1}/{len(tasks)} for {event.name}."},
                        ],
                        task="simple",
                        temperature=0.7,
                    )
                    enriched_tasks.append({
                        **task,
                        "detail": detail if "error" not in detail else None,
                    })
                except Exception as e:
                    logger.warning(f"Task {i+1} enrichment failed: {e}")
                    enriched_tasks.append(task)

            # 更新 DB
            event.tasks = enriched_tasks
            await session.commit()

            logger.info(f"📝 活动内容已增强: {event_code} | {len(enriched_tasks)} tasks")

            return {
                "event_code": event_code,
                "event_name": event.name,
                "tasks": enriched_tasks,
                "task_count": len(enriched_tasks),
            }
