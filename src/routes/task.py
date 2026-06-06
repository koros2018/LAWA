"""
LAWA 任务市场 API 路由

端点：
- GET  /api/v1/tasks           — 任务列表（筛选+分页）
- GET  /api/v1/tasks/{id}      — 任务详情
- POST /api/v1/tasks           — 发布任务
- POST /api/v1/tasks/{id}/accept    — 接单
- POST /api/v1/tasks/{id}/submit    — 提交交付
- POST /api/v1/tasks/{id}/complete  — 验收完成
- POST /api/v1/tasks/{id}/review    — 评价
- POST /api/v1/tasks/ai-draft       — AI 辅助生成初稿
- POST /api/v1/tasks/enforce-deadlines — 强制执行过期任务检查
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.routes.auth import get_current_user
from src.models.user import User
from src.database import get_db
from src.agent.task_agent import TaskAgent
from src.services.task_scheduler import enforce_task_deadlines

router = APIRouter(prefix="/api/v1/tasks", tags=["任务市场"])
task_agent = TaskAgent()


# ── 请求模型 ──
class PublishRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    task_type: str = "other"
    language_pair: Optional[str] = None
    difficulty: int = Field(1, ge=1, le=5)
    reward_coin: int = Field(0, ge=0)
    tags: list = []
    deadline: Optional[str] = None
    generate_ai: bool = False
    content: Optional[str] = None  # AI辅助初稿用
    target_language: Optional[str] = "en"


class AcceptRequest(BaseModel):
    task_id: str
    user_id: str


class SubmitRequest(BaseModel):
    task_id: str
    user_id: str
    content: str
    note: str = ""
    is_ai_assisted: bool = False


class CompleteRequest(BaseModel):
    task_id: str
    user_id: str


class ReviewRequest(BaseModel):
    task_id: str
    user_id: str
    rating: int = Field(5, ge=1, le=5)
    comment: str = ""


class AiDraftRequest(BaseModel):
    task_type: str = "translation"
    content: str
    target_language: str = "en"


# ── 端点 ──
@router.get("")
async def list_tasks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """任务列表"""
    return await task_agent.run({
        "action": "list",
        "page": page,
        "limit": limit,
        "status": status,
        "task_type": task_type,
        "user_id": user_id,
        "db": db,
    })


@router.get("/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """任务详情"""
    result = await task_agent.run({"action": "detail", "task_id": task_id, "db": db})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("")
async def publish_task(req: PublishRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """发布任务"""
    result = await task_agent.run({
        "action": "publish",
        "publisher_id": str(current_user.id),
        "title": req.title,
        "description": req.description,
        "task_type": req.task_type,
        "language_pair": req.language_pair,
        "difficulty": req.difficulty,
        "reward_coin": req.reward_coin,
        "tags": req.tags,
        "deadline": req.deadline,
        "generate_ai": req.generate_ai,
        "content": req.content,
        "target_language": req.target_language,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/{task_id}/accept")
async def accept_task(task_id: str, req: AcceptRequest, db: AsyncSession = Depends(get_db)):
    """接单"""
    result = await task_agent.run({
        "action": "accept",
        "task_id": task_id,
        "user_id": req.user_id,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/{task_id}/submit")
async def submit_task(task_id: str, req: SubmitRequest, db: AsyncSession = Depends(get_db)):
    """提交交付"""
    result = await task_agent.run({
        "action": "submit",
        "task_id": task_id,
        "user_id": req.user_id,
        "content": req.content,
        "note": req.note,
        "is_ai_assisted": req.is_ai_assisted,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/{task_id}/complete")
async def complete_task(task_id: str, req: CompleteRequest, db: AsyncSession = Depends(get_db)):
    """验收完成"""
    result = await task_agent.run({
        "action": "complete",
        "task_id": task_id,
        "user_id": req.user_id,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/{task_id}/review")
async def review_task(task_id: str, req: ReviewRequest, db: AsyncSession = Depends(get_db)):
    """评价任务"""
    result = await task_agent.run({
        "action": "review",
        "task_id": task_id,
        "user_id": req.user_id,
        "rating": req.rating,
        "comment": req.comment,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/ai-draft")
async def ai_draft(req: AiDraftRequest):
    """AI辅助生成初稿"""
    return await task_agent.run({
        "action": "ai_draft",
        "task_type": req.task_type,
        "content": req.content,
        "target_language": req.target_language,
    })


@router.post("/enforce-deadlines")
async def enforce_deadlines():
    """手动触发过期任务检查（也可由 cron 定时调用）"""
    result = await enforce_task_deadlines()
    return result
