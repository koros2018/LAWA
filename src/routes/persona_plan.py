"""
LAWA 画像 + 规划 API 路由

端点：
- POST /api/v1/persona/analyze      — 分析用户画像
- POST /api/v1/persona/tutor/init   — 初始化AI导师
- POST /api/v1/plan/weekly          — 生成周计划
- POST /api/v1/plan/daily           — 生成每日任务
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.main import get_db
from src.agent.persona_agent import PersonaAgent
from src.agent.plan_agent import PlanAgent

router = APIRouter(prefix="/api/v1", tags=["画像与规划"])
persona_agent = PersonaAgent()
plan_agent = PlanAgent()


# ── 请求模型 ──
class AnalyzePersonaRequest(BaseModel):
    user_id: Optional[str] = None
    lang: str = Field("en", pattern="^(en|zh)$")
    native_lang: str = "zh"
    learn_lang: str = "en"
    level: str = "B1"
    assessment_summary: Optional[str] = None
    dimension_scores: dict = {}
    questionnaire: dict = {}


class InitTutorRequest(BaseModel):
    user_id: Optional[str] = None
    persona_summary: str = ""
    learn_lang: str = "en"
    level: str = "B1"
    weaknesses: list[str] = []
    learning_style: dict = {}


class WeeklyPlanRequest(BaseModel):
    user_id: Optional[str] = None
    learn_lang: str = "en"
    native_lang: str = "zh"
    level: str = "B1"
    target_level: str = "B2"
    strengths: list[str] = []
    weaknesses: list[str] = []
    interests: list[str] = ["daily_life"]
    learning_style: dict = {}
    daily_minutes: int = 30
    best_time: str = "evening"


class DailyTasksRequest(BaseModel):
    user_id: Optional[str] = None
    learn_lang: str = "en"
    level: str = "B1"
    focus_areas: list[str] = ["grammar", "vocabulary", "speaking"]
    theme: str = "Daily Practice"
    count: int = 3
    learning_style: dict = {}
    date: Optional[str] = None


# ── 画像端点 ──
@router.post("/persona/analyze")
async def analyze_persona(req: AnalyzePersonaRequest):
    """分析用户学习画像"""
    result = await persona_agent.run({
        "action": "analyze_persona",
        "user_id": req.user_id,
        "lang": req.lang,
        "native_lang": req.native_lang,
        "learn_lang": req.learn_lang,
        "level": req.level,
        "assessment_summary": req.assessment_summary,
        "dimension_scores": req.dimension_scores,
        "questionnaire": req.questionnaire,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/persona/tutor/init")
async def init_tutor(req: InitTutorRequest):
    """初始化AI导师"""
    result = await persona_agent.run({
        "action": "init_tutor",
        "user_id": req.user_id,
        "persona_summary": req.persona_summary,
        "learn_lang": req.learn_lang,
        "level": req.level,
        "weaknesses": req.weaknesses,
        "learning_style": req.learning_style,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ── 规划端点 ──
@router.post("/plan/weekly")
async def generate_weekly_plan(req: WeeklyPlanRequest):
    """生成7天学习计划"""
    result = await plan_agent.run({
        "action": "generate_weekly_plan",
        "user_id": req.user_id,
        "learn_lang": req.learn_lang,
        "native_lang": req.native_lang,
        "level": req.level,
        "target_level": req.target_level,
        "strengths": req.strengths,
        "weaknesses": req.weaknesses,
        "interests": req.interests,
        "learning_style": req.learning_style,
        "daily_minutes": req.daily_minutes,
        "best_time": req.best_time,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/plan/daily")
async def generate_daily_tasks(req: DailyTasksRequest):
    """生成每日任务"""
    result = await plan_agent.run({
        "action": "generate_daily_tasks",
        "user_id": req.user_id,
        "learn_lang": req.learn_lang,
        "level": req.level,
        "focus_areas": req.focus_areas,
        "theme": req.theme,
        "count": req.count,
        "learning_style": req.learning_style,
        "date": req.date,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
