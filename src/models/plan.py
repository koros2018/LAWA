"""
LAWA 学习规划 + 导师数据模型
"""
import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Text, JSON, Boolean, func
from src.models.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base


class LearningPlan(Base):
    """学习计划（周计划）"""
    __tablename__ = "learning_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    lang: Mapped[str] = mapped_column(String(5), nullable=False)  # zh | en

    # 计划内容
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_overview: Mapped[str] = mapped_column(Text, nullable=True)
    weekly_goals: Mapped[list] = mapped_column(JSON, default=list)
    days: Mapped[list] = mapped_column(JSON, default=list)  # [{day, theme, tasks: [...]}, ...]
    weekend_challenge: Mapped[dict] = mapped_column(JSON, nullable=True)

    # 状态
    current_level: Mapped[str] = mapped_column(String(10))
    target_level: Mapped[str] = mapped_column(String(10))
    estimated_weeks: Mapped[int] = mapped_column(Integer, default=12)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DailyTask(Base):
    """每日任务"""
    __tablename__ = "daily_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("learning_plans.id"), nullable=True)

    task_date: Mapped[date] = mapped_column(Date, nullable=False)
    task_type: Mapped[str] = mapped_column(String(20), nullable=False)  # grammar|vocabulary|reading|writing|speaking|listening|review
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=15)
    difficulty: Mapped[str] = mapped_column(String(10), default="medium")
    skill: Mapped[str] = mapped_column(String(20), nullable=True)

    # 完成状态
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_minutes: Mapped[int] = mapped_column(Integer, default=0)
    coins_earned: Mapped[int] = mapped_column(Integer, default=0)
    user_rating: Mapped[int] = mapped_column(Integer, nullable=True)  # 1-5

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TutorProfile(Base):
    """AI导师画像"""
    __tablename__ = "tutor_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)

    tutor_name: Mapped[str] = mapped_column(String(50), default="Alex")
    lang: Mapped[str] = mapped_column(String(5), nullable=False)  # zh | en
    teaching_style: Mapped[str] = mapped_column(String(30), default="patient_explainer")
    personality: Mapped[list] = mapped_column(JSON, default=list)  # ["encouraging", "structured"]
    expertise: Mapped[list] = mapped_column(JSON, default=list)    # ["grammar", "writing"]
    default_strategies: Mapped[list] = mapped_column(JSON, default=list)
    tutor_intro: Mapped[str] = mapped_column(Text, nullable=True)

    # 进化相关
    tutor_vector_seed: Mapped[dict] = mapped_column(JSON, default=dict)  # 初始化向量种子
    sessions_conducted: Mapped[int] = mapped_column(Integer, default=0)   # 教学对话次数
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0)        # 平均评分
    evolution_history: Mapped[list] = mapped_column(JSON, default=list)  # 进化记录
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)      # 是否可被他人租用
    rental_coins: Mapped[int] = mapped_column(Integer, default=0)        # 租用价格

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
