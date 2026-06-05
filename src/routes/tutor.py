"""
LAWA Tutor API — AI伴读导师 (LAWA的灵魂)

端点：
- POST /tutor/onboard        🆕 新用户获得专属导师
- POST /tutor/chat           🆕 与导师实时对话
- POST /tutor/adjust         🆕 调整教学难度
- GET  /tutor/history        🆕 对话历史
- POST /tutor/check-in       🆕 导师主动关怀
- GET  /tutor/profile        获取导师画像
- POST /tutor/evolve         触发导师进化
- GET  /tutor/lesson         生成个性化微课件
- GET  /tutor/insights       学习进度深度洞见
- GET  /tutor/market         可租用导师市场
- POST /tutor/rent           租用导师
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.agent.tutor_agent import TutorAgent

router = APIRouter(prefix="/api/v1/tutor", tags=["AI伴读导师"])
tutor_agent = TutorAgent()


# ═══════════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════════

class OnboardRequest(BaseModel):
    user_id: str
    lang: str = "en"
    learner_name: str = "Learner"


class ChatRequest(BaseModel):
    user_id: str
    message: str = Field(..., min_length=1, max_length=2000)
    context_type: str = "general_chat"
    level: str = "B1"
    learner_name: str = "Learner"


class AdjustRequest(BaseModel):
    user_id: str
    direction: str = Field(..., description="easier | harder")
    reason: str = ""


class CheckInRequest(BaseModel):
    user_id: str


class EvolveRequest(BaseModel):
    user_id: str
    lang: str = "en"
    current_profile: dict = {}
    learning_data: dict = {}


class LessonFeedbackRequest(BaseModel):
    user_id: str
    lesson_id: str
    rating: int = Field(ge=1, le=5)
    completed: bool = True
    time_spent_minutes: int = 0
    notes: str = ""


class RentRequest(BaseModel):
    user_id: str
    tutor_id: str
    rental_coins: int = 0


# ═══════════════════════════════════════════════
# 🆕 POST /tutor/onboard — 新用户获得专属导师
# ═══════════════════════════════════════════════
@router.post("/onboard")
async def onboard_tutor(body: OnboardRequest, db: AsyncSession = Depends(get_db)):
    """为新用户创建独一无二的AI导师人格"""
    result = await tutor_agent.run({
        "action": "onboard",
        "user_id": body.user_id,
        "lang": body.lang,
        "learner_name": body.learner_name,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════════════
# 🆕 POST /tutor/chat — 与导师实时对话
# ═══════════════════════════════════════════════
@router.post("/chat")
async def chat_with_tutor(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    """与你的AI导师进行1v1对话"""
    result = await tutor_agent.run({
        "action": "chat",
        "user_id": body.user_id,
        "message": body.message,
        "context_type": body.context_type,
        "level": body.level,
        "learner_name": body.learner_name,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════════════
# 🆕 POST /tutor/adjust — 调整教学难度
# ═══════════════════════════════════════════════
@router.post("/adjust")
async def adjust_difficulty(body: AdjustRequest, db: AsyncSession = Depends(get_db)):
    """告诉导师调整难度：太简单 / 太难"""
    result = await tutor_agent.run({
        "action": "adjust",
        "user_id": body.user_id,
        "direction": body.direction,
        "reason": body.reason,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════════════
# 🆕 GET /tutor/history — 对话历史
# ═══════════════════════════════════════════════
@router.get("/history")
async def get_chat_history(
    user_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取与导师的对话历史"""
    result = await tutor_agent.run({
        "action": "history",
        "user_id": user_id,
        "limit": limit,
        "db": db,
    })
    return result


# ═══════════════════════════════════════════════
# 🆕 POST /tutor/check-in — 导师主动关怀
# ═══════════════════════════════════════════════
@router.post("/check-in")
async def tutor_check_in(body: CheckInRequest, db: AsyncSession = Depends(get_db)):
    """导师主动问候用户 — 可用于定时任务触发"""
    result = await tutor_agent.run({
        "action": "check_in",
        "user_id": body.user_id,
        "db": db,
    })
    return result


# ═══════════════════════════════════════════════
# GET /tutor/profile
# ═══════════════════════════════════════════════
@router.get("/profile")
async def get_tutor_profile(
    user_id: str = Query(...),
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
):
    """获取该用户的AI导师画像"""
    result = await tutor_agent.run({
        "action": "get_profile",
        "user_id": user_id,
        "lang": lang,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════════════
# POST /tutor/evolve
# ═══════════════════════════════════════════════
@router.post("/evolve")
async def evolve_tutor(body: EvolveRequest):
    """分析学习数据，进化导师策略"""
    result = await tutor_agent.run({
        "action": "evolve",
        "user_id": body.user_id,
        "current_profile": body.current_profile,
        "learning_data": body.learning_data,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    if result.get("evolution_record"):
        result["evolution_record"]["timestamp"] = datetime.now(timezone.utc).isoformat()
    return result


# ═══════════════════════════════════════════════
# GET /tutor/lesson
# ═══════════════════════════════════════════════
@router.get("/lesson")
async def generate_lesson(
    user_id: str = Query(...),
    lang: str = Query("en"),
    level: str = Query("B1"),
    focus_topic: Optional[str] = Query(None),
    difficulty: str = Query("adaptive"),
):
    """生成一份个性化微课件"""
    result = await tutor_agent.run({
        "action": "generate_lesson",
        "user_id": user_id,
        "lang": lang,
        "level": level,
        "weak_areas": [],
        "learning_style": {},
        "focus_topic": focus_topic,
        "difficulty": difficulty,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════════════
# POST /tutor/lesson/feedback
# ═══════════════════════════════════════════════
@router.post("/lesson/feedback")
async def submit_lesson_feedback(body: LessonFeedbackRequest):
    """提交微课件反馈"""
    return {
        "user_id": body.user_id,
        "lesson_id": body.lesson_id,
        "rating": body.rating,
        "status": "recorded",
        "message": "反馈已记录。",
    }


# ═══════════════════════════════════════════════
# GET /tutor/insights
# ═══════════════════════════════════════════════
@router.get("/insights")
async def get_learning_insights(
    user_id: str = Query(...),
    lang: str = Query("en"),
    current_level: str = Query("B1"),
    target_level: str = Query("B2"),
    total_sessions: int = Query(0),
    total_minutes: int = Query(0),
):
    """分析学习数据，生成深度洞见"""
    result = await tutor_agent.run({
        "action": "get_insights",
        "user_id": user_id,
        "lang": lang,
        "current_level": current_level,
        "target_level": target_level,
        "total_sessions": total_sessions,
        "total_minutes": total_minutes,
        "top_skills": [],
        "top_errors": [],
        "progress_data": {},
        "vocab_mastered": 0,
        "vocab_total": 0,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════════════
# GET /tutor/market
# ═══════════════════════════════════════════════
@router.get("/market")
async def get_tutor_market(
    lang: str = Query("en"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    """浏览可租用的导师列表"""
    result = await tutor_agent.run({
        "action": "list_public",
        "lang": lang,
        "page": page,
        "limit": limit,
    })
    return result


# ═══════════════════════════════════════════════
# POST /tutor/rent
# ═══════════════════════════════════════════════
@router.post("/rent")
async def rent_tutor(body: RentRequest):
    """租用一个导师（扣除金币）"""
    result = await tutor_agent.run({
        "action": "rent",
        "user_id": body.user_id,
        "tutor_id": body.tutor_id,
        "rental_coins": body.rental_coins,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
