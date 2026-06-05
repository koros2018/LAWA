"""
LAWA RPG 任务与副本系统数据模型

核心表：
- QuestTemplate: 任务模板库（日常/周常/主线/副本）
- UserQuest: 用户任务实例
- DungeonInstance: 副本实例
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Boolean, func
from src.models.compat import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class QuestTemplate(Base):
    """任务模板库"""
    __tablename__ = "quest_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    quest_type: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")  # daily|weekly|main|side|dungeon|raid
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    skill_focus: Mapped[str] = mapped_column(String(20), nullable=True)  # grammar|vocabulary|reading|writing|speaking
    cefr_min: Mapped[str] = mapped_column(String(5), nullable=True)
    cefr_max: Mapped[str] = mapped_column(String(5), nullable=True)
    xp_reward: Mapped[int] = mapped_column(Integer, default=20)
    coin_reward: Mapped[int] = mapped_column(Integer, default=5)
    item_reward_codes: Mapped[list] = mapped_column(ARRAY(Text), default=list)
    pre_quest_code: Mapped[str] = mapped_column(String(30), nullable=True)  # 前置任务code
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=True)  # 限时
    content: Mapped[dict] = mapped_column(JSON, default=dict)  # 任务具体内容
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserQuest(Base):
    """用户任务实例"""
    __tablename__ = "user_quests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    quest_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quest_templates.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="accepted")  # accepted|in_progress|completed|failed|expired
    progress: Mapped[dict] = mapped_column(JSON, default=dict)  # {"answered": 3, "correct": 2}
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class DungeonInstance(Base):
    """副本实例（多人/限时挑战）"""
    __tablename__ = "dungeon_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quest_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quest_templates.id"), nullable=False)
    host_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    participant_ids: Mapped[list] = mapped_column(ARRAY(Text), default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")  # waiting|active|completed|failed
    current_phase: Mapped[int] = mapped_column(Integer, default=1)
    team_score: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
