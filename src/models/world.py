"""
LAWA RPG 世界地图数据模型

核心表：
- LanguageZone: 语言区域（华夏区/英美区）
- ZoneNode: 区域内场景（城市/建筑/副本入口）
- ZoneConnection: 区域间通道

RPG世界系统核心 —— 替代原有 home_zone 单字段
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, func
from src.models.compat import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class LanguageZone(Base):
    """语言区域（大洲级别）"""
    __tablename__ = "language_zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)   # "en-uk", "zh-cn"
    name: Mapped[str] = mapped_column(String(100), nullable=False)               # "英美联邦"
    culture_theme: Mapped[str] = mapped_column(String(50), nullable=True)        # "维多利亚蒸汽朋克"
    native_lang: Mapped[str] = mapped_column(String(5), nullable=False)          # "en"
    unlock_requirement: Mapped[str] = mapped_column(String(20), nullable=True)   # "CEFR B1" / "HSK3"
    map_position: Mapped[dict] = mapped_column(JSON, default=dict)               # {"x": 120, "y": 80}
    connected_zones: Mapped[list] = mapped_column(ARRAY(Text), default=list)     # 相邻区域 codes
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ZoneNode(Base):
    """区域内具体场景"""
    __tablename__ = "zone_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("language_zones.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)   # "london-grammar-guild"
    name: Mapped[str] = mapped_column(String(100), nullable=False)               # "伦敦语法公会"
    node_type: Mapped[str] = mapped_column(String(20), nullable=False, default="city")  # city|dungeon|market|academy
    skill_focus: Mapped[str] = mapped_column(String(20), nullable=True)          # grammar|reading|writing|speaking
    cefr_min: Mapped[str] = mapped_column(String(5), nullable=True)              # 最低进入等级
    cefr_max: Mapped[str] = mapped_column(String(5), nullable=True)              # 推荐最高等级
    daily_quest_pool: Mapped[list] = mapped_column(ARRAY(Text), default=list)    # 可生成的日常任务模板 codes
    npc_dialogue: Mapped[dict] = mapped_column(JSON, default=dict)               # 区域NPC对话脚本
    description: Mapped[str] = mapped_column(String(500), nullable=True)          # 场景描述
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ZoneConnection(Base):
    """区域间通道"""
    __tablename__ = "zone_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("language_zones.id"), nullable=False)
    to_zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("language_zones.id"), nullable=False)
    travel_cost: Mapped[int] = mapped_column(Integer, default=0)                  # 金币消耗
    travel_time: Mapped[int] = mapped_column(Integer, default=0)                  # 虚拟时间（秒）
    unlock_condition: Mapped[str] = mapped_column(String(100), nullable=True)     # "完成B1评估" / "拥有航海图道具"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
