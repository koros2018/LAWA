"""
LAWA AI导师数据模型

核心概念：
- TutorPersona: 每位用户独有的AI导师人格 — 名字/性格/幽默风格/教学风格
- TutorConversation: 用户与导师的对话记录（含上下文类型标记）
- TutorMemoryNote: 导师对用户的学习记忆 — "这个用户怕写作"、"上次解释了虚拟语气"
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Boolean, func
from src.models.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base


class TutorPersona(Base):
    """AI导师人格 — 每个用户拥有独一无二的导师"""
    __tablename__ = "tutor_personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # ── 导师身份 ──
    tutor_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="导师名字，如 'Captain Grammar'")
    lang: Mapped[str] = mapped_column(String(5), nullable=False, default="en")

    # ── 教学风格 ──
    teaching_style: Mapped[str] = mapped_column(String(30), nullable=False, default="patient_explainer")
    # patient_explainer | drill_master | conversationalist | storyteller | grammar_nerd | coach | cheerleader

    # ── 人格特质 (JSON array) ──
    personality: Mapped[list] = mapped_column(JSON, default=lambda: ["encouraging", "witty", "patient"])

    # ── 幽默风格 ──
    humor_style: Mapped[str] = mapped_column(String(30), default="light_puns")
    # light_puns | dad_jokes | witty_banter | dry_sarcasm | motivational | playful_teasing

    # ── 语气 ──
    voice_tone: Mapped[str] = mapped_column(String(30), default="warm_professional")
    # warm_professional | enthusiastic_coach | calm_mentor | strict_teacher | cheerleader | socratic

    # ── 专精领域 ──
    expertise: Mapped[list] = mapped_column(JSON, default=lambda: ["grammar", "vocabulary", "reading"])

    # ── 默认教学策略 ──
    default_strategies: Mapped[list] = mapped_column(JSON, default=lambda: [
        "error_correction_with_explanation",
        "scenario_based_learning",
    ])

    # ── 统计数据 ──
    sessions_conducted: Mapped[int] = mapped_column(Integer, default=0)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    avg_rating: Mapped[float] = mapped_column(default=0.0)
    current_difficulty: Mapped[str] = mapped_column(String(10), default="adaptive")
    # adaptive | easier | harder | custom

    # ── 导师自我描述 ──
    tutor_intro: Mapped[str] = mapped_column(Text, nullable=True, comment="导师自我介绍")
    avatar_emoji: Mapped[str] = mapped_column(String(10), default="🦉")

    # ── 公开/市场 ──
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    rental_coins: Mapped[int] = mapped_column(Integer, default=0)

    # ── 进化历史 ──
    evolution_history: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TutorConversation(Base):
    """导师对话记录"""
    __tablename__ = "tutor_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    persona_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tutor_personas.id"), nullable=False)

    # ── 对话内容 ──
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # user | tutor
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # ── 上下文标记 ──
    context_type: Mapped[str] = mapped_column(String(30), default="general_chat")
    # general_chat | struggle_help | difficulty_adjust | grammar_explain | vocab_help
    # | writing_feedback | speaking_practice | check_in | lesson_followup

    # ── 元数据（JSON扩展） ──
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class TutorMemoryNote(Base):
    """导师对用户的记忆笔记 — '上次解释了虚拟语气，他还是不太懂'"""
    __tablename__ = "tutor_memory_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    persona_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tutor_personas.id"), nullable=False)

    # ── 记忆内容 ──
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    # weakness | strength | preference | milestone | joke_landed | joke_failed
    note: Mapped[str] = mapped_column(Text, nullable=False)

    # ── 重要性权重 ──
    importance: Mapped[int] = mapped_column(Integer, default=1, comment="1-5，越高越重要")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_recalled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    recall_count: Mapped[int] = mapped_column(Integer, default=0)
