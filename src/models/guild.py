"""
LAWA RPG 公会系统数据模型

Guild/Clan: 语言学习公会
- 公会等级影响成员上限和 buff
- 公会贡献驱动公会升级
- 公会任务由全体成员协作完成
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, JSON, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from src.database.main import Base


def _newid() -> str:
    return str(uuid.uuid4())


class LanguageGuild(Base):
    """语言公会"""
    __tablename__ = "language_guilds"

    id = Column(String(36), primary_key=True, default=_newid)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(Text, default="")
    language = Column(String(5), nullable=False, comment="公会主语言 zh/en")
    level = Column(Integer, default=1, comment="公会等级(1-50)")
    xp = Column(Integer, default=0, comment="公会经验值")
    member_count = Column(Integer, default=0)
    member_limit = Column(Integer, default=10, comment="当前等级成员上限")
    guild_hall_level = Column(Integer, default=1)
    buffs = Column(JSON, default=lambda: {})
    emblem = Column(String(10), default="🛡️")
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    co_owner_ids = Column(JSON, default=lambda: [])
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class GuildMember(Base):
    """公会成员"""
    __tablename__ = "guild_members"

    id = Column(String(36), primary_key=True, default=_newid)
    guild_id = Column(String(36), ForeignKey("language_guilds.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    role = Column(String(20), default="member", comment="owner/co_owner/member")
    contribution = Column(Integer, default=0, comment="个人贡献值")
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    guild = relationship("LanguageGuild", backref="members")


class GuildTask(Base):
    """公会任务（协作完成）"""
    __tablename__ = "guild_tasks"

    id = Column(String(36), primary_key=True, default=_newid)
    guild_id = Column(String(36), ForeignKey("language_guilds.id"), nullable=False)
    quest_template_id = Column(String(36), ForeignKey("quest_templates.id"), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    target_value = Column(Integer, default=100, comment="目标完成量")
    current_value = Column(Integer, default=0, comment="当前完成量")
    status = Column(String(20), default="active", comment="active/completed/expired")
    xp_reward = Column(Integer, default=100)
    coin_reward = Column(Integer, default=50)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)

    guild = relationship("LanguageGuild", backref="tasks")


# Guild 等级配置
GUILD_LEVEL_CONFIG = [
    {"level": 1,  "xp_required": 0,    "member_limit": 10,  "buff_bonus_pct": 0},
    {"level": 2,  "xp_required": 100,  "member_limit": 15,  "buff_bonus_pct": 2},
    {"level": 3,  "xp_required": 300,  "member_limit": 20,  "buff_bonus_pct": 5},
    {"level": 4,  "xp_required": 600,  "member_limit": 25,  "buff_bonus_pct": 8},
    {"level": 5,  "xp_required": 1000, "member_limit": 30,  "buff_bonus_pct": 10},
    {"level": 10, "xp_required": 5000, "member_limit": 50,  "buff_bonus_pct": 20},
    {"level": 20, "xp_required": 20000,"member_limit": 80,  "buff_bonus_pct": 30},
    {"level": 50, "xp_required": 100000,"member_limit":200, "buff_bonus_pct": 50},
]

def get_guild_level_config(level: int) -> dict:
    """获取指定等级的配置"""
    cfg = GUILD_LEVEL_CONFIG[0]
    for c in GUILD_LEVEL_CONFIG:
        if c["level"] <= level:
            cfg = c
    return cfg

def calc_guild_xp_for_next_level(level: int) -> int:
    """计算升级所需 XP"""
    for c in GUILD_LEVEL_CONFIG:
        if c["level"] > level:
            return c["xp_required"]
    return GUILD_LEVEL_CONFIG[-1]["xp_required"] * 2  # 50级以上
