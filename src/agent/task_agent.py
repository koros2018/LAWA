"""
LAWA TaskAgent — 任务市场 Agent

管理完整任务生命周期：
- 发布任务 / 接单 / 提交 / 验收 / 评价
- AI辅助生成初稿（翻译/润色/摘要）
- 任务列表 + 筛选
- 金币自动结算
- DB 持久化（优先）+ in-memory 降级
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from src.agent.base_agent import BaseAgent
from src.services.llm_service import LLMService
from src.models.task import Task, TaskSubmission, TaskReview, TaskStatus, TaskType


class TaskAgent(BaseAgent):
    """任务市场核心Agent"""

    AI_ASSIST_PROMPTS = {
        "translation": "请将以下内容翻译成{target}：\n\n{content}\n\n翻译结果：",
        "proofreading": "请润色以下{lang}文本，修正语法和表达问题，保持原意：\n\n{content}\n\n润色后：",
        "summary": "请用{lang}总结以下内容，突出要点（150字以内）：\n\n{content}\n\n摘要：",
        "writing": "请帮助撰写以下内容，语言为{lang}：\n\n{content}\n\n撰写结果：",
    }

    def __init__(self):
        super().__init__("TaskAgent")
        self._tasks: dict[str, dict] = {}
        self._llm = LLMService()

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "list")
        handlers = {
            "publish": self.publish_task,
            "accept": self.accept_task,
            "submit": self.submit_task,
            "complete": self.complete_task,
            "review": self.review_task,
            "list": self.list_tasks,
            "ai_draft": self.generate_ai_draft,
            "detail": self.get_detail,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"未知操作: {action}"}
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    # ── 工具方法 ──
    @staticmethod
    def _task_to_dict(t: Task) -> dict:
        """DB 模型 → 前端字典"""
        return {
            "id": str(t.id),
            "publisher_id": str(t.publisher_id),
            "assignee_id": str(t.assignee_id) if t.assignee_id else None,
            "title": t.title,
            "description": t.description or "",
            "task_type": t.task_type.value if hasattr(t.task_type, 'value') else t.task_type,
            "status": t.status.value if hasattr(t.status, 'value') else t.status,
            "language_pair": t.language_pair,
            "difficulty": t.difficulty,
            "reward_coin": t.reward_coin,
            "tags": t.tags or [],
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "ai_draft": t.ai_draft,
            "submissions": [
                {
                    "id": str(s.id),
                    "task_id": str(s.task_id),
                    "user_id": str(s.user_id),
                    "content": s.content,
                    "note": s.note,
                    "is_ai_assisted": s.is_ai_assisted,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in (t.submissions or [])
            ],
            "reviews": [
                {
                    "id": str(r.id),
                    "task_id": str(r.task_id),
                    "reviewer_id": str(r.reviewer_id),
                    "rating": r.rating,
                    "comment": r.comment,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in (t.reviews or [])
            ],
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }

    # ── 任务发布 ──
    async def publish_task(self, payload: dict) -> dict:
        db: Optional[AsyncSession] = payload.get("db")
        task_type = payload.get("task_type", "other")

        # AI辅助生成初稿
        ai_draft = None
        if payload.get("generate_ai", False) and payload.get("content"):
            ai_result = await self._generate_draft(
                task_type=task_type,
                content=payload["content"],
                target_lang=payload.get("target_language", "en"),
            )
            ai_draft = ai_result

        # DB 持久化
        if db and payload.get("publisher_id"):
            try:
                t = Task(
                    publisher_id=uuid.UUID(payload["publisher_id"]),
                    title=payload["title"],
                    description=payload.get("description", ""),
                    task_type=TaskType(task_type) if task_type in [e.value for e in TaskType] else TaskType.other,
                    status=TaskStatus.open,
                    language_pair=payload.get("language_pair"),
                    difficulty=payload.get("difficulty", 1),
                    reward_coin=payload.get("reward_coin", 0),
                    tags=payload.get("tags", []),
                    deadline=datetime.fromisoformat(payload["deadline"]) if payload.get("deadline") else None,
                    ai_draft=ai_draft,
                )
                db.add(t)
                await db.commit()
                await db.refresh(t)
                logger.info(f"📋 任务发布(DB): {t.title} (id={t.id})")
                return {"status": "ok", "task": self._task_to_dict(t)}
            except Exception as e:
                logger.warning(f"任务持久化失败 (降级到内存): {e}")
                await db.rollback()

        # 降级：内存存储
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "publisher_id": payload["publisher_id"],
            "assignee_id": None,
            "title": payload["title"],
            "description": payload.get("description", ""),
            "task_type": task_type,
            "status": "open",
            "language_pair": payload.get("language_pair"),
            "difficulty": payload.get("difficulty", 1),
            "reward_coin": payload.get("reward_coin", 0),
            "tags": payload.get("tags", []),
            "deadline": payload.get("deadline"),
            "ai_draft": ai_draft,
            "submissions": [],
            "reviews": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._tasks[task_id] = task
        logger.info(f"📋 任务发布(MEM): {task['title']}")
        return {"status": "ok", "task": task}

    # ── 接单 ──
    async def accept_task(self, payload: dict) -> dict:
        task_id = payload["task_id"]
        user_id = payload["user_id"]
        db: Optional[AsyncSession] = payload.get("db")

        # DB 路径
        if db:
            try:
                result = await db.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
                t = result.scalar_one_or_none()
                if not t:
                    return {"error": "任务不存在"}
                if t.status != TaskStatus.open:
                    return {"error": f"任务状态为 {t.status.value}，无法接单"}
                if str(t.publisher_id) == user_id:
                    return {"error": "不能接自己的任务"}

                t.status = TaskStatus.assigned
                t.assignee_id = uuid.UUID(user_id)
                t.updated_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(t)
                logger.info(f"🤝 任务接单(DB): {t.title} → user={user_id[:8]}")
                return {"status": "ok", "task": self._task_to_dict(t)}
            except Exception as e:
                logger.warning(f"接单持久化失败 (降级): {e}")
                await db.rollback()

        # 降级：内存
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "任务不存在"}
        if task["status"] != "open":
            return {"error": f"任务状态为 {task['status']}，无法接单"}
        if task["publisher_id"] == user_id:
            return {"error": "不能接自己的任务"}
        task["status"] = "assigned"
        task["assignee_id"] = user_id
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        return {"status": "ok", "task": task}

    # ── 提交交付 ──
    async def submit_task(self, payload: dict) -> dict:
        task_id = payload["task_id"]
        user_id = payload["user_id"]
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                result = await db.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
                t = result.scalar_one_or_none()
                if not t:
                    return {"error": "任务不存在"}
                if str(t.assignee_id) != user_id:
                    return {"error": "你不是任务承接人"}

                sub = TaskSubmission(
                    task_id=t.id,
                    user_id=uuid.UUID(user_id),
                    content=payload.get("content", ""),
                    note=payload.get("note", ""),
                    is_ai_assisted=payload.get("is_ai_assisted", False),
                )
                db.add(sub)
                t.status = TaskStatus.submitted
                t.updated_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(t)
                logger.info(f"📤 任务提交(DB): {t.title}")
                return {"status": "ok", "task": self._task_to_dict(t)}
            except Exception as e:
                logger.warning(f"提交持久化失败 (降级): {e}")
                await db.rollback()

        # 降级
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "任务不存在"}
        submission = {
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "user_id": user_id,
            "content": payload.get("content", ""),
            "note": payload.get("note", ""),
            "is_ai_assisted": payload.get("is_ai_assisted", False),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        task.setdefault("submissions", []).append(submission)
        task["status"] = "submitted"
        return {"status": "ok", "task": task, "submission": submission}

    # ── 验收完成 ──
    async def complete_task(self, payload: dict) -> dict:
        task_id = payload["task_id"]
        user_id = payload["user_id"]
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                result = await db.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
                t = result.scalar_one_or_none()
                if not t:
                    return {"error": "任务不存在"}
                if str(t.publisher_id) != user_id:
                    return {"error": "只有发布者可以验收"}
                if t.status != TaskStatus.submitted:
                    return {"error": "任务尚未提交"}

                t.status = TaskStatus.completed
                t.updated_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(t)
                logger.info(f"✅ 任务验收(DB): {t.title}, 支付={t.reward_coin}🪙")
                return {
                    "status": "ok",
                    "task": self._task_to_dict(t),
                    "payout": {"from": str(t.publisher_id), "to": str(t.assignee_id), "amount": t.reward_coin},
                }
            except Exception as e:
                logger.warning(f"验收持久化失败 (降级): {e}")
                await db.rollback()

        # 降级
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "任务不存在"}
        task["status"] = "completed"
        return {"status": "ok", "task": task, "payout": {"from": task["publisher_id"], "to": task["assignee_id"], "amount": task["reward_coin"]}}

    # ── 评价 ──
    async def review_task(self, payload: dict) -> dict:
        task_id = payload["task_id"]
        user_id = payload["user_id"]
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                result = await db.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
                t = result.scalar_one_or_none()
                if not t:
                    return {"error": "任务不存在"}
                if t.status != TaskStatus.completed:
                    return {"error": "任务未完成，无法评价"}
                if user_id not in (str(t.publisher_id), str(t.assignee_id)):
                    return {"error": "只有参与方可以评价"}

                r = TaskReview(
                    task_id=t.id,
                    reviewer_id=uuid.UUID(user_id),
                    rating=payload.get("rating", 5),
                    comment=payload.get("comment", ""),
                )
                db.add(r)
                await db.commit()
                await db.refresh(t)
                logger.info(f"⭐ 任务评价(DB): {t.title}")
                return {"status": "ok", "task": self._task_to_dict(t)}
            except Exception as e:
                logger.warning(f"评价持久化失败 (降级): {e}")
                await db.rollback()

        # 降级
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "任务不存在"}
        review = {
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "reviewer_id": user_id,
            "rating": payload.get("rating", 5),
            "comment": payload.get("comment", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        task.setdefault("reviews", []).append(review)
        return {"status": "ok", "review": review}

    # ── 任务列表 ──
    async def list_tasks(self, payload: dict) -> dict:
        status_filter = payload.get("status")
        type_filter = payload.get("task_type")
        page = payload.get("page", 1)
        limit = payload.get("limit", 20)
        user_id = payload.get("user_id")
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                query = select(Task)
                if status_filter:
                    try:
                        query = query.where(Task.status == TaskStatus(status_filter))
                    except ValueError:
                        pass
                if type_filter:
                    try:
                        query = query.where(Task.task_type == TaskType(type_filter))
                    except ValueError:
                        pass
                if user_id:
                    uid = uuid.UUID(user_id)
                    query = query.where((Task.publisher_id == uid) | (Task.assignee_id == uid))

                # 总数
                count_q = select(func.count()).select_from(Task)
                if status_filter:
                    try:
                        count_q = count_q.where(Task.status == TaskStatus(status_filter))
                    except ValueError:
                        pass
                count_result = await db.execute(count_q)
                total = count_result.scalar() or 0

                # 分页
                query = query.order_by(Task.created_at.desc()).offset((page - 1) * limit).limit(limit)
                result = await db.execute(query)
                tasks = result.scalars().all()

                return {
                    "tasks": [self._task_to_dict(t) for t in tasks],
                    "total": total,
                    "page": page,
                    "total_pages": max(1, (total + limit - 1) // limit),
                }
            except Exception as e:
                logger.warning(f"任务列表查询失败 (降级): {e}")

        # 降级：内存
        tasks = list(self._tasks.values())
        if status_filter:
            tasks = [t for t in tasks if t["status"] == status_filter]
        if type_filter:
            tasks = [t for t in tasks if t["task_type"] == type_filter]
        if user_id:
            tasks = [t for t in tasks if t["publisher_id"] == user_id or t.get("assignee_id") == user_id]
        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        total = len(tasks)
        start = (page - 1) * limit
        return {
            "tasks": tasks[start:start + limit],
            "total": total,
            "page": page,
            "total_pages": max(1, (total + limit - 1) // limit),
        }

    # ── 任务详情 ──
    async def get_detail(self, payload: dict) -> dict:
        task_id = payload["task_id"]
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                result = await db.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
                t = result.scalar_one_or_none()
                if t:
                    return {"task": self._task_to_dict(t)}
            except Exception as e:
                logger.warning(f"任务详情查询失败 (降级): {e}")

        task = self._tasks.get(task_id)
        if not task:
            return {"error": "任务不存在"}
        return {"task": task}

    # ── AI初稿生成 ──
    async def generate_ai_draft(self, payload: dict) -> dict:
        task_type = payload.get("task_type", "translation")
        content = payload.get("content", "")
        target_lang = payload.get("target_language", "en")
        draft = await self._generate_draft(task_type, content, target_lang)
        return {"status": "ok", "draft": draft}

    async def _generate_draft(self, task_type: str, content: str, target_lang: str) -> str:
        prompt_template = self.AI_ASSIST_PROMPTS.get(task_type)
        if not prompt_template:
            return ""
        lang_map = {"en": "英文", "zh": "中文", "zh-CN": "中文"}
        target = lang_map.get(target_lang, target_lang)
        prompt = prompt_template.format(target=target, lang=target, content=content)
        try:
            result = await self._llm.generate(prompt)
            return result.strip()
        except Exception as e:
            logger.warning(f"AI draft generation failed: {e}")
            return ""
