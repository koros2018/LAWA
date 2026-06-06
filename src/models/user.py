"""
LAWA 用户模型

继承 EMA 用户体系，扩展 LAWA 专用字段：
- 语言选择（母语 + 学习语言）
- 金币余额
- 用户画像（学习风格、兴趣、弱项、服务能力）
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, func
from src.models.compat import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.main import Base


class User(Base):
    """基础用户（复用 EMA 模式）"""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关联
    lawa_profile: Mapped["LawaProfile"] = relationship(back_populates="user", uselist=False)
    password_resets: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user", lazy="selectin")


class LawaProfile(Base):
    """LAWA 用户扩展画像"""
    __tablename__ = "lawa_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)

    # 语言
    native_lang: Mapped[str] = mapped_column(String(5), nullable=False)    # zh | en | fr | de
    learn_lang: Mapped[str] = mapped_column(String(5), nullable=False)     # zh | en | fr | de
    current_level: Mapped[str] = mapped_column(String(5), nullable=True)  # A1~C2 / HSK1~6
    target_level: Mapped[str] = mapped_column(String(5), nullable=True)

    # 能力画像
    skills: Mapped[dict] = mapped_column(JSON, default=dict)             # {"grammar": "B1", "reading": "B2", ...}
    learning_style: Mapped[str] = mapped_column(String(20), nullable=True)  # visual | auditory | reading | kinesthetic
    interests: Mapped[list] = mapped_column(ARRAY(Text), default=list)
    time_preference: Mapped[dict] = mapped_column(JSON, default=dict)    # {"morning": True, "evening": True}
    weak_areas: Mapped[list] = mapped_column(ARRAY(Text), default=list)  # ["writing", "pronunciation"]
    can_help: Mapped[list] = mapped_column(ARRAY(Text), default=list)    # 🆕 我能帮别人什么

    # 金币
    total_coins: Mapped[int] = mapped_column(Integer, default=0)

    # 学习统计
    total_study_minutes: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_login_days: Mapped[int] = mapped_column(Integer, default=0)

    # 🧭 RPG 角色系统（方案C）
    character_class: Mapped[str] = mapped_column(String(30), nullable=True)  # 创业者/金融从业者/工程师/互联网观察员/国际观察员
    xp: Mapped[int] = mapped_column(Integer, default=0)                       # 经验值
    level: Mapped[int] = mapped_column(Integer, default=1)                    # 角色等级
    talent_points: Mapped[int] = mapped_column(Integer, default=0)            # 未分配天赋点
    skill_tree: Mapped[dict] = mapped_column(JSON, default=dict)              # {"grammar": 3, "reading": 5, ...}
    title: Mapped[str] = mapped_column(String(50), nullable=True)             # 称号
    avatar_config: Mapped[dict] = mapped_column(JSON, default=dict)           # 角色外观

    # 🧭 世界地图
    home_zone: Mapped[str] = mapped_column(String(20), nullable=True)         # 归属语言区域（保留兼容）
    current_zone_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=True)   # 当前位置(zone_nodes.id)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关联
    user: Mapped["User"] = relationship(back_populates="lawa_profile")


class PasswordResetToken(Base):
    """密码重置令牌"""
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="password_resets")
