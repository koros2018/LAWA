"""角色系统路由"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from src.routes.auth import get_current_user
from src.models.user import User
from src.agent.character_agent import CharacterAgent, CHARACTER_CLASSES

router = APIRouter(prefix="/character", tags=["RPG-Character"])
character_agent = CharacterAgent()


class AddXPRequest(BaseModel):
    user_id: str
    source: str = "study_10min"
    amount: int = 5


class ChooseClassRequest(BaseModel):
    user_id: str
    class_key: str


class AllocateTalentRequest(BaseModel):
    user_id: str
    skill: str
    points: int = 1


class SetTitleRequest(BaseModel):
    user_id: str
    title: str


@router.get("/classes")
async def list_classes():
    """列出所有可选职业"""
    return {"classes": CHARACTER_CLASSES}


@router.get("/{user_id}")
async def get_character(user_id: str):
    """获取角色面板"""
    result = await character_agent.run({"action": "get_profile", "user_id": user_id})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("/{user_id}/xp")
async def get_xp(user_id: str):
    """获取经验值信息"""
    result = await character_agent.run({"action": "get_xp", "user_id": user_id})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("/{user_id}/stats")
async def get_stats(user_id: str):
    """获取角色统计"""
    result = await character_agent.run({"action": "get_stats", "user_id": user_id})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/xp")
async def add_xp(req: AddXPRequest):
    """增加经验值（自动处理升级）"""
    result = await character_agent.run({
        "action": "add_xp",
        "user_id": req.user_id,
        "source": req.source,
        "amount": req.amount,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/class")
async def choose_class(req: ChooseClassRequest):
    """选择职业"""
    result = await character_agent.run({
        "action": "choose_class",
        "user_id": req.user_id,
        "class_key": req.class_key,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/talent")
async def allocate_talent(req: AllocateTalentRequest):
    """分配天赋点"""
    result = await character_agent.run({
        "action": "allocate_talent",
        "user_id": req.user_id,
        "skill": req.skill,
        "points": req.points,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/title")
async def set_title(req: SetTitleRequest):
    """设置称号"""
    result = await character_agent.run({
        "action": "set_title",
        "user_id": req.user_id,
        "title": req.title,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
