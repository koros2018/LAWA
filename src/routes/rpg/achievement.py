"""成就系统路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from src.agent.achievement_agent import AchievementAgent

router = APIRouter(prefix="/achievements", tags=["RPG-Achievement"])
achievement_agent = AchievementAgent()


class TrackProgressRequest(BaseModel):
    user_id: str
    type: str = "counter"
    code: str = ""
    value: int = 1


class CheckUnlockRequest(BaseModel):
    user_id: str


@router.get("")
async def list_achievements(category: str = "all"):
    """成就列表"""
    return await achievement_agent.run({"action": "list", "category": category})


@router.get("/my")
async def my_achievements(user_id: str):
    """我的成就"""
    return await achievement_agent.run({"action": "my", "user_id": user_id})


@router.post("/track")
async def track_progress(req: TrackProgressRequest):
    """追踪进度"""
    result = await achievement_agent.run({
        "action": "track", "user_id": req.user_id,
        "type": req.type, "code": req.code, "value": req.value,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/badges")
async def my_badges(user_id: str):
    """我的徽章"""
    return await achievement_agent.run({"action": "badges", "user_id": user_id})


@router.post("/check")
async def check_unlock(req: CheckUnlockRequest):
    """检查解锁条件"""
    result = await achievement_agent.run({"action": "check_unlock", "user_id": req.user_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result