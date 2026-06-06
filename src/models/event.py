"""
LAWA RPG 文化节日 & 限时活动

CulturalEvent: 活动模板（节日/限时副本/挑战赛）
UserEvent: 用户参与记录
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, JSON, DateTime, ForeignKey, Boolean
from src.database.main import Base


def _newid() -> str:
    return str(uuid.uuid4())


class CulturalEvent(Base):
    """文化活动 & 限时副本"""
    __tablename__ = "cultural_events"

    id = Column(String(36), primary_key=True, default=_newid)
    code = Column(String(40), unique=True, nullable=False)
    name = Column(String(80), nullable=False)
    emoji = Column(String(5), default="🎉")
    description = Column(Text, default="")
    event_type = Column(String(20), nullable=False, comment="festival/limited_dungeon/challenge")
    zone_code = Column(String(20), nullable=True, comment="关联语言区")
    start_date = Column(DateTime, nullable=True, comment="活动开始时间")
    end_date = Column(DateTime, nullable=True, comment="活动结束时间")
    requirement_level = Column(Integer, default=1, comment="最低等级要求")
    requirement_quest = Column(String(40), nullable=True, comment="前置任务code")
    tasks = Column(JSON, default=list, comment="活动任务列表 [{desc, type, target, xp, coins}]")
    rewards = Column(JSON, default=dict, comment="完成奖励 {xp, coins, items}")
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserEvent(Base):
    """用户活动参与记录"""
    __tablename__ = "user_events"

    id = Column(String(36), primary_key=True, default=_newid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    event_id = Column(String(36), ForeignKey("cultural_events.id"), nullable=False)
    task_index = Column(Integer, default=0, comment="当前任务序号")
    task_progress = Column(Integer, default=0, comment="当前任务进度")
    completed_tasks = Column(JSON, default=list, comment="已完成任务序号列表")
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════
#  种子数据
# ═══════════════════════════════════════

SEED_EVENTS = [
    {
        "code": "spring_festival",
        "name": "春节语言庙会",
        "emoji": "🧧",
        "description": "用中文拜年、写春联、讲年俗故事，在春节氛围中提升语言能力！",
        "event_type": "festival",
        "zone_code": "cn",
        "requirement_level": 1,
        "tasks": [
            {"desc": "用目标语言说一句新年祝福", "type": "speak", "target": 1, "xp": 20, "coins": 10},
            {"desc": "写一副春联或新年贺卡", "type": "write", "target": 1, "xp": 30, "coins": 15},
            {"desc": "阅读一篇春节文化文章并回答", "type": "read", "target": 1, "xp": 25, "coins": 10},
            {"desc": "讲述一个你家乡的过年习俗", "type": "speak", "target": 1, "xp": 50, "coins": 25},
        ],
        "rewards": {"xp": 200, "coins": 100, "items": ["spring_couplet_scroll"]},
    },
    {
        "code": "mid_autumn",
        "name": "中秋诗词大会",
        "emoji": "🥮",
        "description": "赏月吟诗，翻译古诗词，感受中秋文化的诗意之美。",
        "event_type": "festival",
        "zone_code": "cn",
        "requirement_level": 3,
        "tasks": [
            {"desc": "朗读一首与月亮有关的诗", "type": "speak", "target": 1, "xp": 20, "coins": 10},
            {"desc": "将一首中文古诗翻译成英文", "type": "translate", "target": 1, "xp": 40, "coins": 20},
            {"desc": "写一段关于中秋的短文（100字以上）", "type": "write", "target": 100, "xp": 50, "coins": 25},
        ],
        "rewards": {"xp": 150, "coins": 80, "items": ["mooncake_token"]},
    },
    {
        "code": "business_negotiation",
        "name": "跨国商务谈判挑战",
        "emoji": "💼",
        "description": "限时副本！模拟跨国商务谈判，用外语争取最优合同条款。",
        "event_type": "limited_dungeon",
        "zone_code": "en",
        "requirement_level": 10,
        "requirement_quest": "daily_001",
        "tasks": [
            {"desc": "准备英文商务提案大纲", "type": "write", "target": 1, "xp": 30, "coins": 15},
            {"desc": "模拟谈判对话（5轮交互）", "type": "speak", "target": 5, "xp": 60, "coins": 30},
            {"desc": "撰写英文合同摘要", "type": "write", "target": 1, "xp": 50, "coins": 25},
        ],
        "rewards": {"xp": 300, "coins": 150, "items": ["golden_pen"]},
        "start_date": None,  # 随时可开
        "end_date": None,
    },
    {
        "code": "reading_marathon",
        "name": "外文阅读马拉松",
        "emoji": "📚",
        "description": "7天内完成7篇外文文章阅读，解锁阅读达人徽章！",
        "event_type": "challenge",
        "zone_code": "en",
        "requirement_level": 5,
        "tasks": [
            {"desc": "阅读一篇英文新闻并写摘要", "type": "read", "target": 1, "xp": 15, "coins": 8},
            {"desc": "阅读一篇英文短篇小说章节", "type": "read", "target": 1, "xp": 20, "coins": 10},
            {"desc": "阅读一篇英文学术论文摘要", "type": "read", "target": 1, "xp": 25, "coins": 12},
            {"desc": "撰写一篇读书笔记（200字以上）", "type": "write", "target": 200, "xp": 40, "coins": 20},
        ],
        "rewards": {"xp": 250, "coins": 120, "items": ["bookworm_badge"]},
    },
    {
        "code": "christmas_carols",
        "name": "圣诞歌曲翻译赛",
        "emoji": "🎄",
        "description": "翻译经典圣诞歌曲，在节日氛围中练习语言韵律感！",
        "event_type": "festival",
        "zone_code": "en",
        "requirement_level": 2,
        "tasks": [
            {"desc": "听一首英文圣诞歌并写出歌词大意", "type": "listen", "target": 1, "xp": 20, "coins": 10},
            {"desc": "翻译一段歌词保持押韵", "type": "translate", "target": 1, "xp": 35, "coins": 18},
            {"desc": "用目标语言写一段节日祝福", "type": "write", "target": 1, "xp": 25, "coins": 12},
        ],
        "rewards": {"xp": 180, "coins": 90, "items": ["jingle_bell"]},
    },
]
