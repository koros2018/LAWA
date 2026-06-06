"""
LAWA 伴读数据模型

CompanionSession — 伴读会话
CompanionMessage — 对话消息（含纠错+生词标注）
CompanionVocabulary — 用户生词本（含间隔复习）
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, func
)
from src.models.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.main import Base


class CompanionSession(Base):
    """伴读会话"""
    __tablename__ = "companion_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    lang: Mapped[str] = mapped_column(String(5), nullable=False)  # en | zh
    scenario_id: Mapped[str] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed | abandoned

    # 会话统计
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    user_message_count: Mapped[int] = mapped_column(Integer, default=0)
    total_corrections: Mapped[int] = mapped_column(Integer, default=0)
    total_vocabulary: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # 金币记录
    coins_earned: Mapped[int] = mapped_column(Integer, default=0)

    # 会话总结
    summary: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # 关联消息
    messages: Mapped[list["CompanionMessage"]] = relationship(back_populates="session", order_by="CompanionMessage.created_at")


class CompanionMessage(Base):
    """伴读对话消息"""
    __tablename__ = "companion_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_sessions.id"), nullable=False, index=True)

    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 纠错信息（仅 user 消息）
    corrections: Mapped[list] = mapped_column(JSON, nullable=True)
    # [{"original": "I goes", "corrected": "I go", "type": "grammar", "explanation": "..."}]

    # 生词提取（仅 assistant 消息）
    vocabulary_extracted: Mapped[list] = mapped_column(JSON, nullable=True)
    # [{"word": "ubiquitous", "definition": "无处不在的", "context": "..."}]

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关联
    session: Mapped["CompanionSession"] = relationship(back_populates="messages")


class CompanionVocabulary(Base):
    """用户生词本（含间隔复习调度）"""
    __tablename__ = "companion_vocabulary"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    lang: Mapped[str] = mapped_column(String(5), nullable=False)  # en | zh

    word: Mapped[str] = mapped_column(String(100), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=True)
    part_of_speech: Mapped[str] = mapped_column(String(20), nullable=True)  # noun/verb/adjective...
    example_sentence: Mapped[str] = mapped_column(Text, nullable=True)

    # 来源会话
    source_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)

    # 间隔复习 (Spaced Repetition)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    review_interval_hours: Mapped[float] = mapped_column(Float, default=0)   # 当前间隔
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)          # 难度系数 (SM-2)
    last_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_mastered: Mapped[bool] = mapped_column(Boolean, default=False)        # 是否已掌握

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    class Config:
        indexes = [
            {"fields": ["user_id", "lang", "word"], "unique": True},
        ]
