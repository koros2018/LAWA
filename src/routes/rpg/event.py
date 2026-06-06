"""文化活动 & 限时活动路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from src.agent.event_agent import EventAgent

router = APIRouter(prefix="/events", tags=["RPG-Event"])
event_agent = EventAgent()


class JoinEventRequest(BaseModel):
    user_id: str
    code: str


class EventProgressRequest(BaseModel):
    user_id: str
    code: str
    task_index: int = 0
    value: int = 1


class EventGenerateRequest(BaseModel):
    lang: str = Field(default="en", description="语言")
    event_type: str = Field(default="festival", description="活动类型")
    user_level: Optional[str] = Field(default=None, description="用户等级")
    zone_code: Optional[str] = Field(default=None, description="区域代码")


class EventContentRequest(BaseModel):
    event_code: str = Field(..., description="活动代码")
    lang: str = Field(default="en", description="语言")
    user_level: Optional[str] = Field(default=None, description="用户等级")


@router.get("")
async def list_events(
    event_type: str = "all",
    zone_code: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """活动列表"""
    return await event_agent.run({
        "action": "list", "event_type": event_type,
        "zone_code": zone_code, "user_id": user_id,
    })


@router.get("/my")
async def my_events(user_id: str):
    """我的活动列表"""
    return await event_agent.run({"action": "my", "user_id": user_id})


@router.post("/join")
async def join_event(req: JoinEventRequest):
    """参与活动"""
    result = await event_agent.run({
        "action": "join", "user_id": req.user_id, "code": req.code,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/progress")
async def event_progress(req: EventProgressRequest):
    """提交活动进度"""
    result = await event_agent.run({
        "action": "progress", "user_id": req.user_id,
        "code": req.code, "task_index": req.task_index, "value": req.value,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/{event_code}")
async def event_detail(event_code: str, user_id: Optional[str] = None):
    """活动详情"""
    return await event_agent.run({"action": "detail", "code": event_code, "user_id": user_id})


@router.post("/generate")
async def generate_event(req: EventGenerateRequest):
    """LLM 生成完整文化活动"""
    result = await event_agent.run({
        "action": "generate_event",
        "lang": req.lang,
        "event_type": req.event_type,
        "user_level": req.user_level or ("B1" if req.lang == "en" else "HSK3"),
        "zone_code": req.zone_code or ("en" if req.lang == "en" else "cn"),
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/generate-content")
async def generate_event_content(req: EventContentRequest):
    """LLM 为已有活动生成/增强任务内容"""
    result = await event_agent.run({
        "action": "generate_event_content",
        "event_code": req.event_code,
        "lang": req.lang,
        "user_level": req.user_level or ("B1" if req.lang == "en" else "HSK3"),
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result