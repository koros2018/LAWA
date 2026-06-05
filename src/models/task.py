"""
LAWA 任务市场数据模型

核心表：
- Task: 任务实体（发布/接单/交付/验收）
- TaskSubmission: 任务提交记录
- TaskReview: 任务评价（1-5星+评论）
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Enum as SAEnum, func
from src.models.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
import enum


class TaskType(str, enum.Enum):
    translation = "translation"
    proofreading = "proofreading"
    summary = "summary"
    writing = "writing"
    speaking = "speaking"
    tutoring = "tutoring"
    other = "other"


class TaskStatus(str, enum.Enum):
    open = "open"             # 待接单
    assigned = "assigned"     # 已分配
    submitted = "submitted"   # 已提交
    completed = "completed"   # 已完成
    cancelled = "cancelled"   # 已取消


class Task(Base):
    """任务实体"""
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publisher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    assignee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    task_type: Mapped[TaskType] = mapped_column(SAEnum(TaskType), nullable=False, default=TaskType.other)
    status: Mapped[TaskStatus] = mapped_column(SAEnum(TaskStatus), nullable=False, default=TaskStatus.open, index=True)

    language_pair: Mapped[str] = mapped_column(String(20), nullable=True, comment="如 en→zh, zh→en")
    difficulty: Mapped[int] = mapped_column(Integer, default=1, comment="难度 1-5")
    reward_coin: Mapped[int] = mapped_column(Integer, default=0, comment="悬赏金币")
    tags: Mapped[list] = mapped_column(JSON, default=list, comment="分类标签")

    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_draft: Mapped[str] = mapped_column(Text, nullable=True, comment="AI生成初稿")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    submissions: Mapped[list] = relationship("TaskSubmission", back_populates="task", cascade="all, delete-orphan")
    reviews: Mapped[list] = relationship("TaskReview", back_populates="task", cascade="all, delete-orphan")


class TaskSubmission(Base):
    """任务提交"""
    __tablename__ = "task_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False, comment="提交内容")
    note: Mapped[str] = mapped_column(Text, nullable=True, comment="备注")
    is_ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relations
    task: Mapped["Task"] = relationship("Task", back_populates="submissions")


class TaskReview(Base):
    """任务评价"""
    __tablename__ = "task_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    rating: Mapped[int] = mapped_column(Integer, nullable=False, comment="评分 1-5")
    comment: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relations
    task: Mapped["Task"] = relationship("Task", back_populates="reviews")
