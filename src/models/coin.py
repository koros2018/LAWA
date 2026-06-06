"""
LAWA 金币系统数据模型

核心表：
- CoinTransaction: 每笔金币流水（ACID事务）
- CoinDailySummary: 每日汇总（排行榜数据源）
- HelpRequest: 互助求助帖
- HelpResponse: 互助回答
"""
import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey, Text, JSON, Boolean, func, UniqueConstraint
from src.models.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.main import Base


class CoinTransaction(Base):
    """金币交易流水"""
    __tablename__ = "coin_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # register | daily_login | daily_consume | study | trade_in | trade_out | help_earn | help_spend | invite | reward | penalty

    amount: Mapped[int] = mapped_column(Integer, nullable=False, comment="正=收入, 负=支出")
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    related_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, comment="扩展元数据")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CoinDailySummary(Base):
    """每日金币汇总"""
    __tablename__ = "coin_daily_summaries"
    __table_args__ = (UniqueConstraint("user_id", "summary_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False)

    coins_earned: Mapped[int] = mapped_column(Integer, default=0)
    coins_spent: Mapped[int] = mapped_column(Integer, default=0)
    net_change: Mapped[int] = mapped_column(Integer, default=0)
    ending_balance: Mapped[int] = mapped_column(Integer, nullable=False)

    study_minutes: Mapped[int] = mapped_column(Integer, default=0)
    helped_count: Mapped[int] = mapped_column(Integer, default=0)
    login_count: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
