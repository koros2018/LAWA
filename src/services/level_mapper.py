"""
LAWA 语言等级映射系统

支持：
- CEFR (A1~C2)：英文评估标准
- HSK (1~6级)：中文评估标准
- 双向对标映射
"""
from enum import StrEnum
from typing import Optional


class CEFRLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class HSKLevel(StrEnum):
    HSK1 = "HSK1"
    HSK2 = "HSK2"
    HSK3 = "HSK3"
    HSK4 = "HSK4"
    HSK5 = "HSK5"
    HSK6 = "HSK6"


# ── CEFR 等级描述（英文评估） ──
CEFR_DESCRIPTORS = {
    "A1": {
        "label": "入门级 / Beginner",
        "description": "能理解并使用熟悉的日常表达法和基本词汇。能介绍自己和他人，能问答个人基本信息。",
        "vocabulary": "~500 words",
        "grammar": "基础时态（一般现在时、现在进行时）",
        "reading": "能看懂简单标识、短通知",
        "writing": "能写简单句子、填写表单",
        "speaking": "能简单问候、介绍自己",
    },
    "A2": {
        "label": "基础级 / Elementary",
        "description": "能理解与个人相关领域的大多数句子和常用表达。能在简单日常任务中沟通。",
        "vocabulary": "~1000-1500 words",
        "grammar": "基础时态+情态动词",
        "reading": "能看懂简短简单的文章",
        "writing": "能写简短便条和信息",
        "speaking": "能进行简单的日常对话",
    },
    "B1": {
        "label": "进阶级 / Intermediate",
        "description": "能理解工作、学校、休闲等熟悉事物的清晰标准输入。能在目标语言地区旅行时处理多数情况。",
        "vocabulary": "~2000-2500 words",
        "grammar": "所有主要时态、被动语态、条件句",
        "reading": "能看懂日常文本、简单文章",
        "writing": "能写连贯的文字描述经历",
        "speaking": "能就熟悉话题进行持续对话",
    },
    "B2": {
        "label": "中高级 / Upper Intermediate",
        "description": "能理解具体和抽象主题的复杂文本主旨。能与母语者进行相当流利的互动。",
        "vocabulary": "~3000-4000 words",
        "grammar": "全部语法体系掌握，细微差别正在精进",
        "reading": "能看懂观点性文章和报告",
        "writing": "能写出清晰详细的各类文章",
        "speaking": "能参与讨论并陈述观点",
    },
    "C1": {
        "label": "高级 / Advanced",
        "description": "能理解各类高难度长文本并识别隐含意义。能流利自然地表达而不明显寻找措辞。",
        "vocabulary": "~5000-8000 words",
        "grammar": "语法体系完全掌握，能灵活运用",
        "reading": "能看懂学术文章、专业文献",
        "writing": "能写出结构清晰的复杂文章",
        "speaking": "能流利讨论专业领域话题",
    },
    "C2": {
        "label": "精通级 / Proficient",
        "description": "能轻松理解所看到或听到的一切。能用流畅精准的语言表达自己，能区分复杂情境中的微妙含义。",
        "vocabulary": "~10000+ words",
        "grammar": "母语水平掌握，自然运用",
        "reading": "能看懂几乎所有形式的书面语言",
        "writing": "能写出流畅复杂的各类文体",
        "speaking": "能无困难地参与任何对话或讨论",
    },
}

# ── HSK 等级描述（中文评估） ──
HSK_DESCRIPTORS = {
    "HSK1": {
        "label": "入门级 (HSK 1)",
        "cefr_aligned": "A1",
        "vocabulary": 150,
        "characters": "~150",
        "description": "能理解并使用非常简单的汉语词语和句子。能满足基本的交际需求。",
        "grammar": "基础语序、基本疑问句、量词入门",
        "reading": "能识别基础汉字和拼音",
        "writing": "能写简单汉字",
        "speaking": "能进行最基本的问候和介绍",
    },
    "HSK2": {
        "label": "基础级 (HSK 2)",
        "cefr_aligned": "A2",
        "vocabulary": 300,
        "characters": "~300",
        "description": "能就常见的日常话题进行简单直接的交流。",
        "grammar": "基础补语、比较句、'把'字句入门",
        "reading": "能看懂简单通知和短信",
        "writing": "能写简短便条",
        "speaking": "能进行简单的日常生活对话",
    },
    "HSK3": {
        "label": "初级 (HSK 3)",
        "cefr_aligned": "B1",
        "vocabulary": 600,
        "characters": "~600",
        "description": "能用汉语完成生活、学习、工作的基本交际任务。",
        "grammar": "'把'字句、'被'字句、各类补语",
        "reading": "能看懂简短文章和通知",
        "writing": "能写简单的段落",
        "speaking": "能就熟悉话题进行交流",
    },
    "HSK4": {
        "label": "中级 (HSK 4)",
        "cefr_aligned": "B2",
        "vocabulary": 1200,
        "characters": "~1000",
        "description": "能用汉语就较广泛领域的话题进行讨论，较流利地与母语者交流。",
        "grammar": "复句结构、修辞手法入门",
        "reading": "能看懂一般性文章和新闻",
        "writing": "能写出连贯的短文",
        "speaking": "能比较流利地表达观点",
    },
    "HSK5": {
        "label": "高级 (HSK 5)",
        "cefr_aligned": "C1",
        "vocabulary": 2500,
        "characters": "~1500",
        "description": "能阅读汉语报刊，欣赏汉语影视，用汉语进行较为完整的演讲。",
        "grammar": "复杂句式、成语、修辞",
        "reading": "能看懂较复杂的文章",
        "writing": "能写出结构清晰的长文",
        "speaking": "能进行深度讨论和演讲",
    },
    "HSK6": {
        "label": "精通级 (HSK 6)",
        "cefr_aligned": "C2",
        "vocabulary": 5000,
        "characters": "~2500",
        "description": "能轻松理解听到或读到的汉语信息，以口头或书面形式流利表达。",
        "grammar": "完全掌握，近母语水平",
        "reading": "能看懂专业文献和古典文学",
        "writing": "能写出流畅精美的文章",
        "speaking": "能在任何场景下流利交流",
    },
}

# ── 等级对标映射 ──
CEFR_TO_HSK = {
    "A1": "HSK1",
    "A2": "HSK2",
    "B1": "HSK3",
    "B2": "HSK4",
    "C1": "HSK5",
    "C2": "HSK6",
}

HSK_TO_CEFR = {v: k for k, v in CEFR_TO_HSK.items()}

# ── 评估维度 ──
ASSESSMENT_DIMENSIONS = {
    "en": ["grammar", "vocabulary", "reading", "writing", "speaking"],
    "zh": ["characters", "vocabulary", "grammar", "reading", "writing", "speaking"],
}

DIMENSION_LABELS = {
    "grammar": "语法",
    "vocabulary": "词汇",
    "reading": "阅读",
    "writing": "写作",
    "speaking": "口语",
    "characters": "汉字",
}

# ── 等级数值映射（用于计算差距） ──
LEVEL_NUMERIC = {
    "A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6,
    "HSK1": 1, "HSK2": 2, "HSK3": 3, "HSK4": 4, "HSK5": 5, "HSK6": 6,
}


def get_level_gap(current: str, target: str) -> int:
    """计算两等级差距（正值=目标更高）"""
    return LEVEL_NUMERIC.get(target, 0) - LEVEL_NUMERIC.get(current, 0)


def hsk_to_cefr(hsk_level: str) -> Optional[str]:
    """HSK → CEFR 等级映射"""
    return HSK_TO_CEFR.get(hsk_level)


def cefr_to_hsk(cefr_level: str) -> Optional[str]:
    """CEFR → HSK 等级映射"""
    return CEFR_TO_HSK.get(cefr_level)


def get_level_descriptor(level: str, lang: str = "en") -> dict:
    """获取等级描述"""
    if lang == "en" and level in CEFR_DESCRIPTORS:
        return CEFR_DESCRIPTORS[level]
    if lang == "zh" and level in HSK_DESCRIPTORS:
        return HSK_DESCRIPTORS[level]
    return {}
