"""
LAWA 社区 API 路由（排行榜 + 匹配 + 互助）
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.main import get_db
from src.agent.leaderboard_agent import LeaderboardAgent
from src.agent.match_agent import MatchAgent
from src.agent.help_agent import HelpAgent
from src.agent.guild_agent import GuildAgent
from src.routes.auth import get_current_user
from src.models.user import User

router = APIRouter(prefix="/api/v1/community", tags=["社区"])
leaderboard_agent = LeaderboardAgent()
match_agent = MatchAgent()
help_agent = HelpAgent()
guild_agent = GuildAgent()


# ── 请求模型 ──
class RecordScoreRequest(BaseModel):
    user_id: str
    board_type: str = "coins"
    score: float = 1


class RegisterProfileRequest(BaseModel):
    user_id: str
    native_language: str = "zh-CN"
    target_language: str = "en"
    level: str = "A2"
    interests: list = []
    learning_style: str = "visual"
    bio: str = ""


class FindPartnersRequest(BaseModel):
    user_id: str
    limit: int = 10


class PostHelpRequest(BaseModel):
    user_id: str
    title: str = Field(..., min_length=1, max_length=200)
    content: str = ""
    language: str = "en"
    tags: list = []
    reward_coin: int = 0


class RespondHelpRequest(BaseModel):
    request_id: str
    user_id: str
    content: str


class AcceptHelpRequest(BaseModel):
    request_id: str
    user_id: str
    response_id: str


# ── 排行榜 ──
@router.post("/leaderboard/record")
async def record_score(req: RecordScoreRequest, db: AsyncSession = Depends(get_db)):
    return await leaderboard_agent.run({
        "action": "record",
        "user_id": req.user_id,
        "board_type": req.board_type,
        "score": req.score,
    })


@router.get("/leaderboard/{board_type}")
async def get_leaderboard(
    board_type: str,
    period: str = Query("daily", pattern="^(daily|weekly|all)$"),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await leaderboard_agent.run({
        "action": "get_board",
        "board_type": board_type,
        "period": period,
        "limit": limit,
        "user_id": user_id,
    })


@router.get("/leaderboard/rank/{user_id}")
async def get_rank(user_id: str, db: AsyncSession = Depends(get_db)):
    return await leaderboard_agent.run({
        "action": "get_rank",
        "user_id": user_id,
    })


# ── 匹配 ──
@router.post("/match/register")
async def register_match_profile(req: RegisterProfileRequest, db: AsyncSession = Depends(get_db)):
    return await match_agent.run({
        "action": "register",
        "user_id": req.user_id,
        "native_language": req.native_language,
        "target_language": req.target_language,
        "level": req.level,
        "interests": req.interests,
        "learning_style": req.learning_style,
        "bio": req.bio,
    })


@router.post("/match/find")
async def find_partners(req: FindPartnersRequest, db: AsyncSession = Depends(get_db)):
    return await match_agent.run({
        "action": "find_partners",
        "user_id": req.user_id,
        "limit": req.limit,
    })


@router.post("/match/pair")
async def match_pair(payload: dict, db: AsyncSession = Depends(get_db)):
    return await match_agent.run({
        "action": "match",
        "user_a": payload.get("user_a"),
        "user_b": payload.get("user_b"),
    })


# ── 互助 ──
@router.post("/help/post")
async def post_help(req: PostHelpRequest):
    result = await help_agent.run({
        "action": "post",
        "user_id": req.user_id,
        "title": req.title,
        "content": req.content,
        "language": req.language,
        "tags": req.tags,
        "reward_coin": req.reward_coin,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/help/respond")
async def respond_help(req: RespondHelpRequest):
    result = await help_agent.run({
        "action": "respond",
        "request_id": req.request_id,
        "user_id": req.user_id,
        "content": req.content,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/help/accept")
async def accept_help(req: AcceptHelpRequest):
    result = await help_agent.run({
        "action": "accept",
        "request_id": req.request_id,
        "user_id": req.user_id,
        "response_id": req.response_id,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/help")
async def list_help(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    language: Optional[str] = None,
    user_id: Optional[str] = None,
):
    return await help_agent.run({
        "action": "list", "page": page, "limit": limit,
        "status": status, "language": language, "user_id": user_id,
    })


@router.get("/help/{request_id}")
async def get_help(request_id: str):
    result = await help_agent.run({"action": "detail", "request_id": request_id})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


# ── 公会 ──
@router.get("/guilds")
async def list_guilds(language: str = "en", name: str = "", db: AsyncSession = Depends(get_db)):
    """获取公会列表"""
    result = await guild_agent.run({"action": "list", "language": language, "name": name, "db": db})
    return result


@router.get("/guild/my")
async def my_guild(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取我的公会"""
    result = await guild_agent.run({"action": "my_guild", "user_id": str(current_user.id), "db": db})
    return result


@router.get("/guild/{guild_id}")
async def guild_detail(guild_id: str, db: AsyncSession = Depends(get_db)):
    """获取公会详情"""
    result = await guild_agent.run({"action": "detail", "guild_id": guild_id, "db": db})
    return result


@router.post("/guild/create")
async def create_guild(req: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """创建公会"""
    result = await guild_agent.run({
        "action": "create",
        "user_id": str(current_user.id),
        "name": req.get("name", ""),
        "language": req.get("language", "en"),
        "description": req.get("description", ""),
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/guild/join")
async def join_guild(req: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """加入公会"""
    result = await guild_agent.run({
        "action": "join",
        "user_id": str(current_user.id),
        "guild_id": req.get("guild_id", ""),
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/guild/leave")
async def leave_guild(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """离开公会"""
    result = await guild_agent.run({"action": "leave", "user_id": str(current_user.id), "db": db})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
