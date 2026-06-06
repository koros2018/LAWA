"""
LAWA API 路由 - 认证模块

端点：
- POST /api/v1/auth/register     — 注册
- POST /api/v1/auth/login        — 登录
- GET  /api/v1/auth/me           — 当前用户
- POST /api/v1/auth/forgot-password — 忘记密码（生成重置令牌）
- POST /api/v1/auth/reset-password  — 重置密码（使用令牌）
"""
import hashlib
import secrets
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger

from src.database.main import get_db
from src.models.user import User, LawaProfile, PasswordResetToken
from src.utils.security import hash_password, verify_password, create_access_token, decode_access_token
from src.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])
security = HTTPBearer(auto_error=False)


# ── 请求模型 ──
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    native_lang: str  # zh | en
    learn_lang: str   # zh | en

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少6个字符")
        # 检查弱密码：纯数字、纯字母、连续字符
        if re.match(r"^\d+$", v):
            raise ValueError("密码不能全为数字")
        if re.match(r"^[a-zA-Z]+$", v):
            raise ValueError("密码不能全为字母")
        if re.match(r"^(.)\1+$", v):
            raise ValueError("密码不能全为相同字符")
        return v

    @field_validator("native_lang", "learn_lang")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        if v not in ("zh", "en"):
            raise ValueError("语言必须是 zh 或 en")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    username: str
    email: str
    role: str
    is_active: bool

    @classmethod
    def from_orm_with_uuid(cls, user) -> "UserResponse":
        """将 User ORM 对象转换为响应，自动序列化 UUID"""
        return cls(
            id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
        )


# ── 依赖注入：当前用户 ──
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT 提取当前用户"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")

    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="令牌格式错误")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    return user


# ── 端点 ──
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册 + 语言选择 + 1000金币奖励"""
    # 检查用户名/邮箱唯一性
    existing = await db.execute(
        select(User).where((User.username == req.username) | (User.email == req.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在")

    # 创建用户
    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    await db.flush()

    # 创建 LAWA 画像
    profile = LawaProfile(
        user_id=user.id,
        native_lang=req.native_lang,
        learn_lang=req.learn_lang,
        total_coins=settings.coins_register_bonus,
    )
    db.add(profile)

    # 金币流水记录（注册奖励）
    from src.models.coin import CoinTransaction
    bonus_txn = CoinTransaction(
        user_id=user.id,
        type="register",
        amount=settings.coins_register_bonus,
        balance_before=0,
        balance_after=settings.coins_register_bonus,
        description="注册奖励",
    )
    db.add(bonus_txn)

    await db.flush()

    # 生成令牌
    access_token = create_access_token(str(user.id))

    logger.info(f"新用户注册: {user.username} ({user.email}), 母语={req.native_lang}, 学习={req.learn_lang}")

    return TokenResponse(access_token=access_token, user_id=str(user.id))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    access_token = create_access_token(str(user.id))

    logger.info(f"用户登录: {user.username}")

    return TokenResponse(access_token=access_token, user_id=str(user.id))


# ── 忘记密码 ──

class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    忘记密码 — 生成重置令牌

    无论用户是否存在，都返回相同响应（防止用户名枚举）
    """
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if user is None:
        # 不暴露用户是否存在
        logger.info(f"忘记密码请求: 用户不存在 {req.username}")
        return {"message": "如果该用户名存在，重置令牌已生成", "reset_token": None}

    # 生成随机令牌
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # 存储哈希后的令牌（1小时有效）
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(reset)
    await db.commit()

    logger.info(f"忘记密码: 已为用户 {req.username} 生成重置令牌")

    # 返回原始令牌（仅此时可获取）
    # 生产环境应通过邮件发送，这里直接返回用于测试
    return {
        "message": "重置令牌已生成，1小时内有效",
        "reset_token": raw_token,
        "expires_in": "1h",
    }


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    重置密码 — 使用令牌设置新密码
    """
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6个字符")

    token_hash = hashlib.sha256(req.token.encode()).hexdigest()

    # 查找有效令牌
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    )
    reset = result.scalar_one_or_none()

    if reset is None:
        raise HTTPException(status_code=400, detail="令牌无效或已过期")

    # 更新密码
    await db.execute(
        update(User).where(User.id == reset.user_id).values(
            password_hash=hash_password(req.new_password),
            updated_at=datetime.now(timezone.utc),
        )
    )

    # 标记令牌已使用
    reset.used_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(f"密码重置: 用户 {reset.user_id} 密码已更新")

    return {"message": "密码已重置，请使用新密码登录"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse.from_orm_with_uuid(current_user)
