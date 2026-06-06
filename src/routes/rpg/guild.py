"""公会系统路由"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from src.routes.auth import get_current_user
from src.models.user import User
from src.agent.guild_agent import GuildAgent

router = APIRouter(prefix="/guild", tags=["RPG-Guild"])
guild_agent = GuildAgent()


class CreateGuildRequest(BaseModel):
    user_id: str
    name: str
    language: str = "en"
    description: str = ""
    emblem: str = "🛡️"


class JoinGuildRequest(BaseModel):
    user_id: str
    guild_id: str


class ContributeRequest(BaseModel):
    user_id: str
    amount: int = 10
    source: str = "study"


class TaskProgressRequest(BaseModel):
    guild_id: str
    task_id: str
    value: int = 1


@router.get("")
async def list_guilds(language: str = "en", name: str = ""):
    """列出公会"""
    result = await guild_agent.run({"action": "list", "language": language, "name": name})
    return result


@router.get("/my")
async def my_guild(current_user: User = Depends(get_current_user)):
    """我的公会"""
    result = await guild_agent.run({"action": "my_guild", "user_id": str(current_user.id)})
    return result


@router.get("/{guild_id}")
async def guild_detail(guild_id: str):
    """公会详情"""
    result = await guild_agent.run({"action": "detail", "guild_id": guild_id})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/create")
async def create_guild(req: CreateGuildRequest, current_user: User = Depends(get_current_user)):
    """创建公会"""
    result = await guild_agent.run({
        "action": "create",
        "user_id": str(current_user.id),
        "name": req.name,
        "language": req.language,
        "description": req.description,
        "emblem": req.emblem,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/join")
async def join_guild(req: JoinGuildRequest):
    """加入公会"""
    result = await guild_agent.run({"action": "join", "user_id": req.user_id, "guild_id": req.guild_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/leave")
async def leave_guild(current_user: User = Depends(get_current_user), guild_id: str = ""):
    """离开公会"""
    result = await guild_agent.run({"action": "leave", "user_id": str(current_user.id), "guild_id": guild_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/contribute")
async def contribute(req: ContributeRequest):
    """公会贡献"""
    result = await guild_agent.run({
        "action": "contribute",
        "user_id": req.user_id,
        "amount": req.amount,
        "source": req.source,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/{guild_id}/tasks")
async def guild_tasks(guild_id: str):
    """公会任务列表"""
    result = await guild_agent.run({"action": "tasks", "guild_id": guild_id})
    return result


@router.post("/tasks/progress")
async def guild_task_progress(req: TaskProgressRequest):
    """公会任务进度"""
    result = await guild_agent.run({
        "action": "task_progress",
        "guild_id": req.guild_id,
        "task_id": req.task_id,
        "value": req.value,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
