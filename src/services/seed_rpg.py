"""
LAWA RPG 世界种子数据

初始化语言区域、场景节点、任务模板
"""
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from loguru import logger
from src.database.main import AsyncSessionLocal, init_db
from src.models.world import LanguageZone, ZoneNode, ZoneConnection
from src.models.quest import QuestTemplate
from src.models.user import LawaProfile
from src.models.equipment import CraftRecipe, Consumable, Equipment
from src.models.coin import CoinTransaction


# ── UUID 常量（用于配方引用）─
# 装备ID
EQ_MAGIC_DICT = uuid.UUID("0361cddc-0c4e-4afe-9cf7-2161e33bb5c1")
EQ_TIME_GLASS = uuid.UUID("0ed20d53-3333-4c20-8395-13b8494b8bab")
EQ_TRANSLATOR_EYE = uuid.UUID("c2e1652e-8690-4c74-9dd2-b0e3aefb7338")
EQ_SCHOLAR_ROBE = uuid.UUID("30f18519-8ed7-4e81-a891-5960843abc2c")
EQ_QUILL_OF_TRUTH = uuid.UUID("c7dc66ce-09a8-48fd-9974-6ee7328c101f")
# 消耗品ID
CO_XP_POTION = uuid.UUID("3f5d1ba8-31bd-4dc3-84c2-bc2ffea0f9d8")
CO_DOUBLE_COIN_CARD = uuid.UUID("e69adac0-d544-4738-935e-0d87521d4369")
CO_RETRY_SCROLL = uuid.UUID("a4519051-aa03-4e74-8649-5ac5948453f6")
CO_SPEED_TEA = uuid.UUID("56573a96-0a5d-471f-a66d-d4380cd3fee1")
CO_XP_ELIXIR = uuid.UUID("5300c3bf-8d38-47ed-8e57-0b0ed9b9ad8a")


# ── 华夏区 ID ──
ZH_ZONE_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
EN_ZONE_ID = uuid.UUID("a0000000-0000-0000-0000-000000000002")


# ═══════════════════════════════════════════════
#  语言区域
# ═══════════════════════════════════════════════
ZONES = [
    {
        "id": ZH_ZONE_ID,
        "code": "zh-cn",
        "name": "华夏区",
        "culture_theme": "东方书院·竹林雅集",
        "native_lang": "zh",
        "unlock_requirement": None,  # 中文母语者默认出生点
        "map_position": {"x": 320, "y": 180},
        "connected_zones": ["en-uk"],
    },
    {
        "id": EN_ZONE_ID,
        "code": "en-uk",
        "name": "英美联邦",
        "culture_theme": "维多利亚蒸汽朋克",
        "native_lang": "en",
        "unlock_requirement": "CEFR A2",
        "map_position": {"x": 120, "y": 80},
        "connected_zones": ["zh-cn"],
    },
]


# ═══════════════════════════════════════════════
#  场景节点
# ═══════════════════════════════════════════════
ZONE_NODES = [
    # ── 华夏区 ──
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000001"),
        "zone_id": ZH_ZONE_ID,
        "code": "zh-grammar-academy",
        "name": "翰墨书院",
        "node_type": "academy",
        "skill_focus": "grammar",
        "cefr_min": "HSK1",
        "cefr_max": "HSK3",
        "daily_quest_pool": ["zh-daily-grammar-1", "zh-daily-grammar-2"],
        "npc_dialogue": {"greeting": "欢迎来到翰墨书院，学子。今日可要练习语法？"},
    },
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000002"),
        "zone_id": ZH_ZONE_ID,
        "code": "zh-reading-pavilion",
        "name": "观澜阁",
        "node_type": "city",
        "skill_focus": "reading",
        "cefr_min": "HSK1",
        "cefr_max": "HSK4",
        "daily_quest_pool": ["zh-daily-reading-1", "zh-daily-reading-2"],
        "npc_dialogue": {"greeting": "观澜阁藏书三千，今日想读哪一卷？"},
    },
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000003"),
        "zone_id": ZH_ZONE_ID,
        "code": "zh-writing-studio",
        "name": "墨香斋",
        "node_type": "city",
        "skill_focus": "writing",
        "cefr_min": "HSK2",
        "cefr_max": "HSK5",
        "daily_quest_pool": ["zh-daily-writing-1"],
        "npc_dialogue": {"greeting": "笔墨纸砚已备好，写下你的故事吧。"},
    },
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000004"),
        "zone_id": ZH_ZONE_ID,
        "code": "zh-speaking-market",
        "name": "长安街市",
        "node_type": "market",
        "skill_focus": "speaking",
        "cefr_min": "HSK1",
        "cefr_max": "HSK6",
        "daily_quest_pool": ["zh-daily-speaking-1", "zh-daily-speaking-2"],
        "npc_dialogue": {"greeting": "客官来啦！今日街市热闹，要练练嘴皮子吗？"},
    },
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000005"),
        "zone_id": ZH_ZONE_ID,
        "code": "zh-dungeon-teahouse",
        "name": "龙门茶馆（副本）",
        "node_type": "dungeon",
        "skill_focus": "speaking",
        "cefr_min": "HSK3",
        "cefr_max": "HSK6",
        "daily_quest_pool": ["zh-dungeon-debate"],
        "npc_dialogue": {"greeting": "龙门阵摆起！今天的辩题是……"},
    },
    # ── 英美区 ──
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000006"),
        "zone_id": EN_ZONE_ID,
        "code": "en-grammar-guild",
        "name": "伦敦语法公会",
        "node_type": "academy",
        "skill_focus": "grammar",
        "cefr_min": "A1",
        "cefr_max": "B1",
        "daily_quest_pool": ["en-daily-grammar-1", "en-daily-grammar-2"],
        "npc_dialogue": {"greeting": "Welcome to the Grammar Guild! Ready to master your tenses?"},
    },
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000007"),
        "zone_id": EN_ZONE_ID,
        "code": "en-reading-library",
        "name": "大英图书馆",
        "node_type": "city",
        "skill_focus": "reading",
        "cefr_min": "A2",
        "cefr_max": "B2",
        "daily_quest_pool": ["en-daily-reading-1", "en-daily-reading-2"],
        "npc_dialogue": {"greeting": "Shhh... Pick a book, any book. Let's read together."},
    },
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000008"),
        "zone_id": EN_ZONE_ID,
        "code": "en-writing-chronicle",
        "name": "舰队街纪事报",
        "node_type": "city",
        "skill_focus": "writing",
        "cefr_min": "B1",
        "cefr_max": "C1",
        "daily_quest_pool": ["en-daily-writing-1"],
        "npc_dialogue": {"greeting": "Deadline's in an hour! Can you polish this article?"},
    },
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000009"),
        "zone_id": EN_ZONE_ID,
        "code": "en-speaking-pub",
        "name": "老柴郡酒馆",
        "node_type": "market",
        "skill_focus": "speaking",
        "cefr_min": "A2",
        "cefr_max": "C1",
        "daily_quest_pool": ["en-daily-speaking-1", "en-daily-speaking-2"],
        "npc_dialogue": {"greeting": "Oi mate! Fancy a chat over a pint? 🍺"},
    },
    {
        "id": uuid.UUID("b0000000-0000-0000-0000-000000000010"),
        "zone_id": EN_ZONE_ID,
        "code": "en-dungeon-boardroom",
        "name": "金融城董事会（副本）",
        "node_type": "dungeon",
        "skill_focus": "speaking",
        "cefr_min": "B2",
        "cefr_max": "C2",
        "daily_quest_pool": ["en-dungeon-negotiation"],
        "npc_dialogue": {"greeting": "The board is waiting. Let's close this deal."},
    },
]


# ═══════════════════════════════════════════════
#  任务模板
# ═══════════════════════════════════════════════
QUEST_TEMPLATES = [
    # ── 华夏区日常 ──
    {"code": "zh-daily-grammar-1", "name": "量词大挑战", "quest_type": "daily", "difficulty": 1,
     "skill_focus": "grammar", "cefr_min": "HSK1", "cefr_max": "HSK3", "xp_reward": 20, "coin_reward": 5,
     "description": "选择正确的量词填空：一___书、一___笔、一___桌子", "content": {"type": "multiple_choice", "questions": 5}},
    {"code": "zh-daily-grammar-2", "name": "把字句练习", "quest_type": "daily", "difficulty": 2,
     "skill_focus": "grammar", "cefr_min": "HSK3", "cefr_max": "HSK5", "xp_reward": 25, "coin_reward": 5,
     "description": "将下列句子改写为'把'字句", "content": {"type": "rewrite", "questions": 3}},
    {"code": "zh-daily-reading-1", "name": "成语故事会", "quest_type": "daily", "difficulty": 2,
     "skill_focus": "reading", "cefr_min": "HSK2", "cefr_max": "HSK5", "xp_reward": 25, "coin_reward": 8,
     "description": "阅读一篇成语故事，回答阅读理解问题", "content": {"type": "reading_comprehension", "passage": "守株待兔"}},
    {"code": "zh-daily-reading-2", "name": "新闻速读", "quest_type": "daily", "difficulty": 3,
     "skill_focus": "reading", "cefr_min": "HSK4", "cefr_max": "HSK6", "xp_reward": 30, "coin_reward": 10,
     "description": "阅读一篇短新闻，提取核心信息", "content": {"type": "reading_comprehension", "source": "新闻摘要"}},
    {"code": "zh-daily-writing-1", "name": "日记一则", "quest_type": "daily", "difficulty": 2,
     "skill_focus": "writing", "cefr_min": "HSK2", "cefr_max": "HSK5", "xp_reward": 30, "coin_reward": 10,
     "description": "用中文写一篇100字的日记", "content": {"type": "free_writing", "min_chars": 100, "prompt": "今天发生了什么有趣的事？"}},
    {"code": "zh-daily-speaking-1", "name": "街头问路", "quest_type": "daily", "difficulty": 1,
     "skill_focus": "speaking", "cefr_min": "HSK1", "cefr_max": "HSK3", "xp_reward": 20, "coin_reward": 5,
     "description": "模拟街头对话：向路人问路并听懂指路", "content": {"type": "dialogue", "turns": 3}},
    {"code": "zh-daily-speaking-2", "name": "茶话闲聊", "quest_type": "daily", "difficulty": 3,
     "skill_focus": "speaking", "cefr_min": "HSK3", "cefr_max": "HSK6", "xp_reward": 30, "coin_reward": 10,
     "description": "在茶馆里和NPC闲聊10句以上", "content": {"type": "dialogue", "turns": 10}},
    {"code": "zh-dungeon-debate", "name": "龙门辩论赛", "quest_type": "dungeon", "difficulty": 5,
     "skill_focus": "speaking", "cefr_min": "HSK4", "cefr_max": "HSK6", "xp_reward": 100, "coin_reward": 30,
     "description": "龙门茶馆的周常辩论赛！随机抽辩题，3v3组队", "content": {"type": "debate", "teams": 2, "rounds": 3}},

    # ── 英美区日常 ──
    {"code": "en-daily-grammar-1", "name": "Tense Detective", "quest_type": "daily", "difficulty": 1,
     "skill_focus": "grammar", "cefr_min": "A1", "cefr_max": "B1", "xp_reward": 20, "coin_reward": 5,
     "description": "Identify and fix tense errors in 5 sentences", "content": {"type": "error_correction", "questions": 5}},
    {"code": "en-daily-grammar-2", "name": "Preposition Maze", "quest_type": "daily", "difficulty": 2,
     "skill_focus": "grammar", "cefr_min": "B1", "cefr_max": "B2", "xp_reward": 25, "coin_reward": 5,
     "description": "Fill in the correct prepositions: in/on/at/to/for", "content": {"type": "fill_blank", "questions": 8}},
    {"code": "en-daily-reading-1", "name": "News Flash", "quest_type": "daily", "difficulty": 2,
     "skill_focus": "reading", "cefr_min": "B1", "cefr_max": "B2", "xp_reward": 25, "coin_reward": 8,
     "description": "Read a short news article and answer comprehension questions", "content": {"type": "reading_comprehension", "source": "BBC Learning"}},
    {"code": "en-daily-reading-2", "name": "Shakespeare in a Nutshell", "quest_type": "daily", "difficulty": 4,
     "skill_focus": "reading", "cefr_min": "B2", "cefr_max": "C1", "xp_reward": 35, "coin_reward": 12,
     "description": "Read a simplified Shakespeare excerpt and interpret the meaning", "content": {"type": "reading_comprehension", "passage": "Hamlet's soliloquy (simplified)"}},
    {"code": "en-daily-writing-1", "name": "Dear Diary", "quest_type": "daily", "difficulty": 2,
     "skill_focus": "writing", "cefr_min": "A2", "cefr_max": "B2", "xp_reward": 30, "coin_reward": 10,
     "description": "Write a 150-word journal entry in English", "content": {"type": "free_writing", "min_words": 150, "prompt": "What's something interesting you learned today?"}},
    {"code": "en-daily-speaking-1", "name": "Coffee Shop Chat", "quest_type": "daily", "difficulty": 1,
     "skill_focus": "speaking", "cefr_min": "A1", "cefr_max": "A2", "xp_reward": 20, "coin_reward": 5,
     "description": "Order a coffee and chat with the barista", "content": {"type": "dialogue", "turns": 3}},
    {"code": "en-daily-speaking-2", "name": "Pub Storytelling", "quest_type": "daily", "difficulty": 3,
     "skill_focus": "speaking", "cefr_min": "B1", "cefr_max": "C1", "xp_reward": 30, "coin_reward": 10,
     "description": "Tell an engaging story to the pub crowd (10+ turns)", "content": {"type": "dialogue", "turns": 10}},
    {"code": "en-dungeon-negotiation", "name": "Boardroom Showdown", "quest_type": "dungeon", "difficulty": 5,
     "skill_focus": "speaking", "cefr_min": "B2", "cefr_max": "C2", "xp_reward": 150, "coin_reward": 40,
     "description": "You're leading a high-stakes business negotiation. Convince the board!", "content": {"type": "simulation", "roles": ["CEO", "Investor", "Analyst"], "rounds": 3}},
]


# ── 区域通道 ──
ZONE_CONNECTIONS = [
    {
        "id": uuid.UUID("c0000000-0000-0000-0000-000000000001"),
        "from_zone_id": ZH_ZONE_ID,
        "to_zone_id": EN_ZONE_ID,
        "travel_cost": 50,
        "travel_time": 3600,  # 1小时虚拟时间
        "unlock_condition": "完成B1评估 或 完成3个华夏区日常任务",
    },
    {
        "id": uuid.UUID("c0000000-0000-0000-0000-000000000002"),
        "from_zone_id": EN_ZONE_ID,
        "to_zone_id": ZH_ZONE_ID,
        "travel_cost": 50,
        "travel_time": 3600,
        "unlock_condition": "完成HSK3评估 或 完成3个英美区日常任务",
    },
]


# ═══════════════════════════════════════════════
#  装备
# ═══════════════════════════════════════════════
EQUIPMENTS = [
    {
        "id": str(EQ_MAGIC_DICT),
        "code": "magic-dict",
        "name": "魔法词典",
        "emoji": "📖",
        "description": "自动查询生词，阅读速度+25%",
        "slot": "weapon",
        "rarity": "epic",
        "price_coin": 500,
        "price_guild_contrib": 0,
        "effects": {"reading_speed_bonus": 25, "auto_lookup": True},
        "required_level": 5,
    },
    {
        "id": str(EQ_TIME_GLASS),
        "code": "time-glass",
        "name": "时光沙漏",
        "emoji": "⏳",
        "description": "学习时段效果+30%，持续15分钟",
        "slot": "accessory",
        "rarity": "legendary",
        "price_coin": 1200,
        "price_guild_contrib": 300,
        "effects": {"xp_multiplier": 1.3, "duration_min": 15},
        "required_level": 10,
    },
    {
        "id": str(EQ_TRANSLATOR_EYE),
        "code": "translator-eye",
        "name": "翻译之眼",
        "emoji": "👁️",
        "description": "实时翻译字幕，听力理解+20%",
        "slot": "head",
        "rarity": "rare",
        "price_coin": 300,
        "price_guild_contrib": 100,
        "effects": {"listening_bonus": 20},
        "required_level": 3,
    },
    {
        "id": str(EQ_SCHOLAR_ROBE),
        "code": "scholar-robe",
        "name": "学士长袍",
        "emoji": "🧙",
        "description": "纠错准确率+15%，装备耐久+1",
        "slot": "armor",
        "rarity": "uncommon",
        "price_coin": 150,
        "price_guild_contrib": 0,
        "effects": {"accuracy_bonus": 15},
        "required_level": 1,
    },
    {
        "id": str(EQ_QUILL_OF_TRUTH),
        "code": "quill-of-truth",
        "name": "真言之羽",
        "emoji": "🪶",
        "description": "写作评分+10%，语法建议更精准",
        "slot": "weapon",
        "rarity": "epic",
        "price_coin": 800,
        "price_guild_contrib": 200,
        "effects": {"writing_score_bonus": 10, "grammar_suggestions": True},
        "required_level": 7,
    },
]


# ═══════════════════════════════════════════════
#  消耗品
# ═══════════════════════════════════════════════
CONSUMABLES = [
    {
        "id": str(CO_XP_POTION),
        "code": "xp-potion",
        "name": "经验药水",
        "emoji": "🧪",
        "description": "下次任务经验+50%",
        "price_coin": 100,
        "effect_type": "xp_boost",
        "effect_value": 50,
        "effect_duration_min": 30,
    },
    {
        "id": str(CO_DOUBLE_COIN_CARD),
        "code": "double-coin-card",
        "name": "双倍金币卡",
        "emoji": "💳",
        "description": "30分钟内所有任务金币翻倍",
        "price_coin": 200,
        "effect_type": "coin_double",
        "effect_value": 100,
        "effect_duration_min": 30,
    },
    {
        "id": str(CO_RETRY_SCROLL),
        "code": "retry-scroll",
        "name": "翻错免死金牌",
        "emoji": "🛡️",
        "description": "答错不扣分，保留一次机会",
        "price_coin": 50,
        "effect_type": "retry",
        "effect_value": 1,
        "effect_duration_min": 0,
    },
    {
        "id": str(CO_SPEED_TEA),
        "code": "speed-tea",
        "name": "速效提神茶",
        "emoji": "🍵",
        "description": "任务限时延长50%",
        "price_coin": 80,
        "effect_type": "time_extend",
        "effect_value": 50,
        "effect_duration_min": 15,
    },
    {
        "id": str(CO_XP_ELIXIR),
        "code": "xp-elixir",
        "name": "精英经验精华",
        "emoji": "💎",
        "description": "24小时内全任务经验+100%（稀有）",
        "price_coin": 500,
        "effect_type": "xp_boost",
        "effect_value": 100,
        "effect_duration_min": 1440,
    },
]


# ═══════════════════════════════════════════════
#  配方
# ═══════════════════════════════════════════════
CRAFT_RECIPES = [
    {
        "id": str(uuid.UUID("d0000000-0000-0000-0000-000000000001")),
        "result_item_type": "equipment",
        "result_item_id": str(EQ_TRANSLATOR_EYE),
        "name": "炼金·翻译之眼",
        "description": "用2个学士长袍 + 1瓶经验药水合成翻译之眼",
        "ingredients": {
            "items": [
                {"item_id": str(EQ_SCHOLAR_ROBE), "item_type": "equipment", "quantity": 2},
                {"item_id": str(CO_XP_POTION), "item_type": "consumable", "quantity": 1},
            ]
        },
        "gold_cost": 200,
    },
    {
        "id": str(uuid.UUID("d0000000-0000-0000-0000-000000000002")),
        "result_item_type": "equipment",
        "result_item_id": str(EQ_MAGIC_DICT),
        "name": "炼金·魔法词典",
        "description": "用1个翻译之眼 + 2瓶经验药水 + 300金币合成魔法词典",
        "ingredients": {
            "items": [
                {"item_id": str(EQ_TRANSLATOR_EYE), "item_type": "equipment", "quantity": 1},
                {"item_id": str(CO_XP_POTION), "item_type": "consumable", "quantity": 2},
            ]
        },
        "gold_cost": 300,
    },
    {
        "id": str(uuid.UUID("d0000000-0000-0000-0000-000000000003")),
        "result_item_type": "consumable",
        "result_item_id": str(CO_XP_ELIXIR),
        "name": "炼金·精英经验精华",
        "description": "用3瓶经验药水 + 1张双倍金币卡 + 500金币合成精英经验精华",
        "ingredients": {
            "items": [
                {"item_id": str(CO_XP_POTION), "item_type": "consumable", "quantity": 3},
                {"item_id": str(CO_DOUBLE_COIN_CARD), "item_type": "consumable", "quantity": 1},
            ]
        },
        "gold_cost": 500,
    },
]


# ═══════════════════════════════════════════════
#  执行播种
# ═══════════════════════════════════════════════
async def seed_rpg_world():
    """初始化RPG世界数据（幂等：已有数据则跳过）"""
    logger.info("🌍 开始播种 RPG 世界...")

    async with AsyncSessionLocal() as session:
        # ── 区域 ──
        existing = await session.execute(select(LanguageZone).limit(1))
        if existing.scalar_one_or_none():
            logger.info("语言区域已存在，跳过播种")
            return {"status": "skipped", "message": "数据已存在"}

        for z in ZONES:
            session.add(LanguageZone(**z))
        logger.info(f"✅ 播种 {len(ZONES)} 个语言区域")

        # ── 场景 ──
        for n in ZONE_NODES:
            session.add(ZoneNode(**n))
        logger.info(f"✅ 播种 {len(ZONE_NODES)} 个场景节点")

        # ── 通道 ──
        for c in ZONE_CONNECTIONS:
            session.add(ZoneConnection(**c))
        logger.info(f"✅ 播种 {len(ZONE_CONNECTIONS)} 条区域通道")

        # ── 任务模板 ──
        for q in QUEST_TEMPLATES:
            session.add(QuestTemplate(**q))
        logger.info(f"✅ 播种 {len(QUEST_TEMPLATES)} 个任务模板")

        # ── 装备 ──
        for e in EQUIPMENTS:
            session.add(Equipment(**e))
        logger.info(f"✅ 播种 {len(EQUIPMENTS)} 件装备")

        # ── 消耗品 ──
        for c in CONSUMABLES:
            session.add(Consumable(**c))
        logger.info(f"✅ 播种 {len(CONSUMABLES)} 种消耗品")

        # ── 配方 ──
        for r in CRAFT_RECIPES:
            session.add(CraftRecipe(**r))
        logger.info(f"✅ 播种 {len(CRAFT_RECIPES)} 个配方")

        await session.commit()

    logger.info(f"🎉 RPG世界播种完成！{len(ZONES)}区 {len(ZONE_NODES)}场景 {len(QUEST_TEMPLATES)}任务 {len(EQUIPMENTS)}装备 {len(CONSUMABLES)}消耗品 {len(CRAFT_RECIPES)}配方")
    return {
        "status": "ok",
        "zones": len(ZONES),
        "nodes": len(ZONE_NODES),
        "connections": len(ZONE_CONNECTIONS),
        "quests": len(QUEST_TEMPLATES),
    }


async def seed_rpg_clear():
    """清除RPG世界数据（仅开发用）"""
    async with AsyncSessionLocal() as session:
        await session.execute(delete(ZoneConnection))
        await session.execute(delete(ZoneNode))
        await session.execute(delete(LanguageZone))
        await session.execute(delete(QuestTemplate))
        await session.commit()
    logger.info("🗑️ RPG世界数据已清除")


if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_rpg_world())
