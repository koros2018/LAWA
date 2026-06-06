"""任务 & 副本路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from src.agent.quest_agent import QuestAgent

router = APIRouter(prefix="/quests", tags=["RPG-Quest"])
quest_agent = QuestAgent()


class AcceptQuestRequest(BaseModel):
    user_id: str
    quest_code: str


class SubmitQuestRequest(BaseModel):
    user_id: str
    quest_id: str
    progress: dict = {}


class QuestGenerateRequest(BaseModel):
    quest_code: Optional[str] = None
    lang: str = "en"
    skill_focus: str = "vocabulary"
    user_level: str = "B1"
    quest_type: str = "daily"


@router.get("/available")
async def list_available_quests(
    user_id: str,
    quest_type: Optional[str] = None,
    zone_code: Optional[str] = None,
    cefr_level: Optional[str] = None,
):
    """列出可用任务模板"""
    result = await quest_agent.run({
        "action": "list_available",
        "user_id": user_id,
        "quest_type": quest_type,
        "skill_focus": cefr_level,
        "zone_code": zone_code,
    })
    return result


@router.get("/daily")
async def get_daily_quests(user_id: str):
    """获取今日日常任务"""
    result = await quest_agent.run({"action": "get_daily", "user_id": user_id})
    return result


@router.get("/active")
async def get_active_quests(user_id: str):
    """获取当前进行中的任务"""
    result = await quest_agent.run({"action": "get_active", "user_id": user_id})
    return result


@router.post("/accept")
async def accept_quest(req: AcceptQuestRequest):
    """接取任务"""
    result = await quest_agent.run({
        "action": "accept",
        "user_id": req.user_id,
        "quest_code": req.quest_code,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/submit")
async def submit_quest(req: SubmitQuestRequest):
    """提交任务进度"""
    result = await quest_agent.run({
        "action": "submit",
        "user_id": req.user_id,
        "user_quest_id": req.quest_id,
        "progress": req.progress,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/{quest_id}/complete")
async def complete_quest(quest_id: str, user_id: str):
    """完成任务"""
    result = await quest_agent.run({
        "action": "complete",
        "user_id": user_id,
        "user_quest_id": quest_id,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/generate-content")
async def generate_quest_content(req: QuestGenerateRequest):
    """LLM 动态生成任务内容"""
    result = await quest_agent.run({
        "action": "generate_content",
        "quest_code": req.quest_code,
        "lang": req.lang,
        "skill_focus": req.skill_focus,
        "user_level": req.user_level,
        "quest_type": req.quest_type,
    })
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result


@router.post("/generate-daily")
async def generate_daily_quest_endpoint(req: QuestGenerateRequest):
    """LLM 动态生成一个完整每日任务并写入DB"""
    result = await quest_agent.run({
        "action": "generate_daily_quest",
        "lang": req.lang,
        "skill_focus": req.skill_focus,
        "user_level": req.user_level,
    })
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result