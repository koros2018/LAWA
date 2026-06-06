"""
LAWA 金币 API 路由
from src.routes.auth import get_current_user
from src.models.user import User

端点：
- GET  /api/v1/coin/rules          — 获取金币规则
- GET  /api/v1/coin/balance/{uid}  — 查询余额
- POST /api/v1/coin/register       — 注册奖励
- POST /api/v1/coin/login          — 每日登录
- POST /api/v1/coin/study          — 学习奖励
- POST /api/v1/coin/trade          — 用户交易
- GET  /api/v1/coin/transactions/{uid} — 交易历史
- GET  /api/v1/coin/daily/{uid}    — 当日汇总
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.agent.coin_agent import CoinAgent
from src.routes.auth import get_current_user
from src.models.user import User

router = APIRouter(prefix="/api/v1/coin", tags=["金币系统"])
coin_agent = CoinAgent()


# ── 请求模型 ──
class RegisterBonusRequest(BaseModel):
    user_id: str


class DailyLoginRequest(BaseModel):
    user_id: str


class StudyRewardRequest(BaseModel):
    user_id: str
    minutes: int = Field(..., gt=0, le=240, description="学习分钟数（1-240）")


class TradeRequest(BaseModel):
    from_user_id: str
    to_user_id: str
    amount: int = Field(..., gt=0, le=500, description="交易金额（1-500金币）")
    description: str = ""


# ── 端点 ──
@router.get("/rules")
async def get_rules():
    """获取金币经济规则"""
    return await coin_agent.run({"action": "get_rules"})


@router.get("/balance")
async def get_balance(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """查询当前用户余额"""
    return await coin_agent.run({"action": "get_balance", "user_id": str(current_user.id), "db": db})


@router.post("/register")
async def register_bonus(req: RegisterBonusRequest, db: AsyncSession = Depends(get_db)):
    """注册即送金币"""
    result = await coin_agent.run({"action": "register_bonus", "user_id": req.user_id, "db": db})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/login")
async def daily_login(req: DailyLoginRequest, db: AsyncSession = Depends(get_db)):
    """每日登录"""
    result = await coin_agent.run({"action": "daily_login", "user_id": req.user_id, "db": db})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/study")
async def study_reward(req: StudyRewardRequest, db: AsyncSession = Depends(get_db)):
    """学习赚金币"""
    result = await coin_agent.run({
        "action": "study_reward",
        "user_id": req.user_id,
        "minutes": req.minutes,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/trade")
async def trade(req: TradeRequest, db: AsyncSession = Depends(get_db)):
    """用户间金币交易"""
    result = await coin_agent.run({
        "action": "trade",
        "from_user_id": req.from_user_id,
        "to_user_id": req.to_user_id,
        "amount": req.amount,
        "description": req.description,
        "db": db,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/transactions")
async def get_transactions(limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """查询当前用户交易历史"""
    return await coin_agent.run({
        "action": "get_transactions",
        "user_id": str(current_user.id),
        "limit": limit,
        "db": db,
    })


@router.get("/daily")
async def daily_summary(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """当日金币汇总"""
    return await coin_agent.run({
        "action": "daily_summary",
        "user_id": str(current_user.id),
        "db": db,
    })
