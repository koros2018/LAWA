"""
LAWA 评估 API 路由

端点：
- POST /api/v1/assessment/start       — 启动评估会话
- POST /api/v1/assessment/question    — 生成下一道测试题
- POST /api/v1/assessment/answer      — 提交答案并获取反馈
- POST /api/v1/assessment/report      — 生成评估报告
- GET  /api/v1/assessment/{id}        — 查询评估详情
- GET  /api/v1/assessment/history     — 评估历史
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

# 语言字段：兼容 en / zh / zh-CN
LANG_PATTERN = "^(en|zh|zh-CN)$"
from typing import Optional
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.agent.assessment_agent import AssessmentAgent
from src.database import get_db
from src.models.assessment import Assessment, AssessmentQuestion

router = APIRouter(prefix="/api/v1/assessment", tags=["水平评估"])

# 全局 Agent 实例
assessment_agent = AssessmentAgent()


# ── 请求/响应模型 ──
class StartAssessmentRequest(BaseModel):
    lang: str = Field(..., pattern=LANG_PATTERN, description="评估语言: en=英文, zh=中文")
    user_id: Optional[str] = None


class GenerateQuestionRequest(BaseModel):
    assessment_id: str
    lang: str = Field(..., pattern=LANG_PATTERN)
    dimension: str
    current_level_estimate: str = "B1"
    previous_results: list[dict] = []


class SubmitAnswerRequest(BaseModel):
    assessment_id: str
    question_id: str
    dimension: str
    question_text: str
    question_type: str = "multiple_choice"
    correct_answer: Optional[str] = None
    user_answer: str
    lang: str = Field(..., pattern=LANG_PATTERN)
    current_level_estimate: str = "B1"


class GenerateReportRequest(BaseModel):
    assessment_id: str
    lang: str = Field(..., pattern=LANG_PATTERN)
    all_answers: list[dict]


# ── 端点 ──
@router.post("/start")
async def start_assessment(req: StartAssessmentRequest, db: AsyncSession = Depends(get_db)):
    """启动一个新的评估会话"""
    if req.lang not in ("en", "zh"):
        raise HTTPException(400, "不支持的语言，请选择 'en' 或 'zh'")

    result = await assessment_agent.run({
        "action": "start_assessment",
        "user_id": req.user_id,
        "lang": req.lang,
        "db": db,
    })

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.post("/question")
async def generate_question(req: GenerateQuestionRequest):
    """生成下一道自适应测试题"""
    result = await assessment_agent.run({
        "action": "generate_question",
        "assessment_id": req.assessment_id,
        "lang": req.lang,
        "dimension": req.dimension,
        "current_level_estimate": req.current_level_estimate,
        "previous_results": req.previous_results,
    })

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.post("/answer")
async def submit_answer(req: SubmitAnswerRequest, db: AsyncSession = Depends(get_db)):
    """提交答案并获取评分和反馈"""
    result = await assessment_agent.run({
        "action": "submit_answer",
        "assessment_id": req.assessment_id,
        "question_id": req.question_id,
        "dimension": req.dimension,
        "question_text": req.question_text,
        "question_type": req.question_type,
        "correct_answer": req.correct_answer,
        "user_answer": req.user_answer,
        "lang": req.lang,
        "current_level_estimate": req.current_level_estimate,
        "db": db,
    })

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.post("/report")
async def generate_report(req: GenerateReportRequest, db: AsyncSession = Depends(get_db)):
    """生成综合评估报告"""
    result = await assessment_agent.run({
        "action": "generate_report",
        "assessment_id": req.assessment_id,
        "lang": req.lang,
        "all_answers": req.all_answers,
        "db": db,
    })

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.get("/{assessment_id}")
async def get_assessment(assessment_id: str, db: AsyncSession = Depends(get_db)):
    """查询评估详情（含题目列表）"""
    try:
        uid = uuid.UUID(assessment_id)
    except ValueError:
        raise HTTPException(400, detail=f"无效的评估ID: {assessment_id}")

    result = await db.execute(
        select(Assessment).where(Assessment.id == uid)
    )
    a = result.scalar_one_or_none()
    if a is None:
        raise HTTPException(404, detail="评估记录不存在")

    # 查询关联题目
    q_result = await db.execute(
        select(AssessmentQuestion).where(AssessmentQuestion.assessment_id == uid)
        .order_by(AssessmentQuestion.order_index)
    )
    questions = q_result.scalars().all()

    return {
        "id": str(a.id),
        "user_id": str(a.user_id),
        "lang": a.lang,
        "status": a.status,
        "overall_level": a.overall_level,
        "dimension_scores": a.dimension_scores,
        "total_questions": a.total_questions,
        "answered_questions": a.answered_questions,
        "time_spent_seconds": a.time_spent_seconds,
        "summary": a.summary,
        "strengths": a.strengths,
        "weaknesses": a.weaknesses,
        "recommendations": a.recommendations,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        "questions": [
            {
                "id": str(q.id),
                "dimension": q.dimension,
                "difficulty": q.difficulty,
                "question_type": q.question_type,
                "question_text": q.question_text,
                "options": q.options,
                "user_answer": q.user_answer,
                "is_correct": q.is_correct,
                "score": q.score,
                "llm_feedback": q.llm_feedback,
                "order_index": q.order_index,
            }
            for q in questions
        ],
    }


@router.get("/history/{user_id}")
async def get_assessment_history(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """查询用户评估历史（分页）"""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(400, detail=f"无效的用户ID: {user_id}")

    result = await db.execute(
        select(Assessment)
        .where(Assessment.user_id == uid)
        .order_by(Assessment.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    assessments = result.scalars().all()

    # 总数
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).select_from(Assessment).where(Assessment.user_id == uid)
    )
    total = count_result.scalar() or 0

    return {
        "user_id": user_id,
        "total": total,
        "offset": offset,
        "limit": limit,
        "assessments": [
            {
                "id": str(a.id),
                "lang": a.lang,
                "status": a.status,
                "overall_level": a.overall_level,
                "total_questions": a.total_questions,
                "answered_questions": a.answered_questions,
                "time_spent_seconds": a.time_spent_seconds,
                "summary": a.summary,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in assessments
        ],
    }
