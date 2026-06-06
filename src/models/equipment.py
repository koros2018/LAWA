"""
LAWA RPG 装备与道具系统

Equipment: 学习装备（魔法词典/时光沙漏/翻译之眼等）
Consumable: 消耗品（经验药水/双倍卡/免死金牌等）
UserInventory: 用户背包
CraftRecipe: 合成配方
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, JSON, ForeignKey, DateTime
from src.database.main import Base


def _newid() -> str:
    return str(uuid.uuid4())


class Equipment(Base):
    """装备模板"""
    __tablename__ = "equipment"

    id = Column(String(36), primary_key=True, default=_newid)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(80), nullable=False)
    emoji = Column(String(5), default="📦")
    description = Column(Text, default="")
    slot = Column(String(20), nullable=False, comment="装备槽: head/body/accessory/tool")
    rarity = Column(String(10), default="common", comment="稀有度: common/rare/epic/legendary")
    price_coin = Column(Integer, default=50)
    price_guild_contrib = Column(Integer, default=0)
    effects = Column(JSON, default=lambda: {}, comment="属性加成: {xp_bonus_pct:10, coin_bonus_pct:5}")
    required_level = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Consumable(Base):
    """消耗品模板"""
    __tablename__ = "consumables"

    id = Column(String(36), primary_key=True, default=_newid)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(80), nullable=False)
    emoji = Column(String(5), default="🧪")
    description = Column(Text, default="")
    price_coin = Column(Integer, default=20)
    effect_type = Column(String(20), nullable=False, comment="效果类型: xp_boost/double_coin/retry/speed_up")
    effect_value = Column(Integer, default=100, comment="效果数值")
    effect_duration_min = Column(Integer, default=30, comment="持续时间(分钟)，0=立即生效")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserInventory(Base):
    """用户背包"""
    __tablename__ = "user_inventory"

    id = Column(String(36), primary_key=True, default=_newid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    item_type = Column(String(20), nullable=False, comment="equipment/consumable")
    item_id = Column(String(36), nullable=False, comment="equipment.id or consumable.id")
    quantity = Column(Integer, default=1, comment="数量(消耗品>1，装备固定1)")
    equipped = Column(Integer, default=0, comment="是否装备(仅equipment): 0未装备 1已装备")
    active_until = Column(DateTime, nullable=True, comment="消耗品效果到期时间")
    acquired_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CraftRecipe(Base):
    """合成配方"""
    __tablename__ = "craft_recipes"

    id = Column(String(36), primary_key=True, default=_newid)
    result_item_type = Column(String(20), nullable=False, comment="equipment/consumable")
    result_item_id = Column(String(36), nullable=False)
    name = Column(String(80), nullable=False)
    description = Column(Text, default="")
    ingredients = Column(JSON, nullable=False, comment='[{"item_code":"xp_potion","quantity":2}]')
    gold_cost = Column(Integer, default=100)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# 稀有度配置
RARITY_CONFIG = {
    "common":    {"label": "普通", "color": "#9ca3af", "price_mult": 1.0},
    "rare":      {"label": "稀有", "color": "#3b82f6", "price_mult": 2.5},
    "epic":      {"label": "史诗", "color": "#a855f7", "price_mult": 5.0},
    "legendary": {"label": "传说", "color": "#f59e0b", "price_mult": 10.0},
}
