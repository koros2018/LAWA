"""
LAWA 排行榜系统数据模型
"""
import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, JSON, func, UniqueConstraint
from src.models.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.database.main import Base


class LeaderboardEntry(Base):
    """排行榜分数记录"""
    __tablename__ = "leaderboard_entries"
    __table_args__ = (UniqueConstraint("user_id", "board_type", "period"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    board_type: Mapped[str] = mapped_column(String(30), nullable=False)  # coins | study_time | help_count | tasks_completed
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # daily | weekly | all
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LeaderboardSnapshot(Base):
    """排行榜日快照"""
    __tablename__ = "leaderboard_snapshots"
    __table_args__ = (UniqueConstraint("period", "snapshot_date", "board_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    board_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rankings: Mapped[dict] = mapped_column(JSON, nullable=False)  # [{rank, user_id, score}, ...]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
