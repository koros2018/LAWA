# LAWA 技术架构设计文档

## 📋 文档信息
| 字段 | 内容 |
|------|------|
| 文档编号 | LAWA-ARCH-001 |
| 版本 | v1.0 |
| 日期 | 2026-05-27 |
| 前身 | ELA-ARCH-001（v1.0） |
| 作者 | GDP影子 |

---

## 1. 总体架构

### 1.1 架构分层
```
┌──────────────────────────────────────────────────────────────────┐
│                         客户端层                                  │
│  Vue3 SPA (port 6289)  |  H5  |  微信小程序 (Phase 3)            │
│  多语言界面 i18n: zh-CN / en-US / fr-FR / de-DE (预留)          │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP / WebSocket
┌────────────────────────────▼─────────────────────────────────────┐
│                    API网关层 (FastAPI 6288)                       │
│  JWT + Rate Limit + CORS + i18n检测 + WebSocket管理              │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                Agent编排层 (Main-Agent)                           │
│  LAWAOrchestrator: 意图分析 → 路由 → 执行 → 整合                 │
└┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬────────────────┘
 │     │     │     │     │     │     │     │     │
┌▼──┐ ┌▼───┐ ┌▼───┐ ┌▼───┐ ┌▼───┐ ┌▼───┐ ┌▼───┐ ┌▼───┐ ┌──────┐
│评 │ │伴  │ │规  │ │画  │ │知  │ │金  │ │匹  │ │排行│ │CI/CD │
│估 │ │读  │ │划  │ │像  │ │识  │ │币  │ │配  │ │榜  │ │     │
│Agt│ │Agt │ │Agt │ │Agt │ │库  │ │Agt │ │Agt │ │Agt │ │Agt  │
└┬──┘ └┬───┘ └┬───┘ └┬───┘ └┬───┘ └┬───┘ └┬───┘ └┬───┘ └──────┘
 │     │      │      │      │      │      │      │
┌▼─────▼──────▼──────▼──────▼──────▼──────▼──────▼───────────────┐
│                       基础设施层                                  │
│  LLM: DeepSeek/NVIDIA API/Ollama                               │
│  DB: SQLite → PostgreSQL  |  Redis(缓存/排行榜/匹配队列)         │
│  向量: ChromaDB  |  WebSocket: FastAPI + Redis Pub/Sub          │
│  语音: Whisper(ASR) | Edge-TTS(Fish-Speech)(TTS)                │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 端口规划
| 服务 | 端口 | 说明 |
|------|------|------|
| **LAWA API** | 6288 | FastAPI后端（与EMA 6188隔离） |
| **LAWA UI** | 6289 | Vue3前端 |
| **Redis** | 6379 | 缓存/会话/排行榜/匹配队列 |
| **ChromaDB** | 8002 | 向量数据库 |

### 1.3 与EMA/blueprint-ai的关系
```
blueprint-ai (5188/5189)          ← 图纸解析(源项目)
     │
     ▼
engineering-management-agent (6188/6189)  ← Manus Agent架构(已验证)
     │
     ▼
english-level-agent (6288/6289)   ← 英语提升工具(ELA，已弃用)
     │
     ▼
LAWA (6288/6289)                  ← 全球语言交流平台(当前)
```

**继承自EMA的核心资产：**
- ✅ Multi-Agent编排模式（Main-Agent + Sub-Agent）
- ✅ 用户系统（JWT + SQLite用户管理）
- ✅ LLM模型注册和路由（model_registry.py）
- ✅ LLM超时监督（llm_supervisor.py）
- ✅ FastAPI框架模式 + CORS策略
- ✅ 前端Vue3 + Vite + TS技术栈
- ✅ BaseAgent基类

**LAWA新增核心模块：**
- 🆕 CoinAgent（金币账本+交易+防刷）
- 🆕 MatchAgent（跨语言匹配引擎）
- 🆕 LeaderboardAgent（排行榜计算+推送）
- 🆕 多语言i18n层（前端Vue I18n + 后端Locale）
- 🆕 WebSocket实时通信层
- 🆕 中文评估（HSK标准）

---

## 2. Agent系统详细设计

### 2.1 Main-Agent: LAWAOrchestrator

```python
class LAWAOrchestrator:
    """LAWA主控Agent - 继承EMA BaseAgent模式"""
    
    def __init__(self, user_id: str, user_profile: dict):
        self.user_id = user_id
        self.profile = user_profile
        self.session = SessionContext(user_id)
        self.sub_agents = {
            "assessment": AssessmentAgent(),
            "companion": CompanionAgent(),
            "plan": PlanAgent(),
            "persona": PersonaAgent(),
            "knowledge": KnowledgeAgent(),
            "coin": CoinAgent(),          # 🆕 LAWA新增
            "match": MatchAgent(),         # 🆕 LAWA新增
            "leaderboard": LeaderboardAgent(),  # 🆕 LAWA新增
            "cicd": CICDAgent(),
        }
    
    async def process(self, user_input: dict) -> dict:
        """主入口：意图分析 → 路由 → 执行 → 整合"""
        intent = await self._analyze_intent(user_input)
        result = await self.sub_agents[intent.agent].execute(intent.payload)
        return await self._format_response(result)
```

### 2.2 AssessmentAgent（评估Agent）

**变更：** 支持中英文双语言评估

```python
class AssessmentAgent:
    def __init__(self):
        self.test_types = {
            "en": ["grammar", "reading", "writing", "speaking"],
            "zh": ["character", "vocabulary", "grammar", "reading", "writing"]
        }
        self.cefr_map = CEFRLevelMapper()
        self.hsk_map = HSKLevelMapper()  # 🆕 HSK映射
    
    async def run_full_assessment(self, user: User, lang: str) -> AssessmentReport:
        """完整评估：支持中文(zh)和英文(en)"""
        if lang == "en":
            return await self._assess_english(user)
        elif lang == "zh":
            return await self._assess_chinese(user)  # 🆕
```

### 2.3 CoinAgent（金币Agent）🆕

**职责：** 金币账本管理、收支记录、防刷、日结算

```python
class CoinAgent:
    """金币经济核心Agent"""
    
    # 金币规则常量
    COINS_REGISTER = 1000
    COINS_DAILY_CONSUME = 10
    COINS_DAILY_LOGIN = 10
    COINS_STUDY_PER_10MIN = 1
    COINS_STUDY_DAILY_MAX = 12  # 2小时上限
    COINS_INVITE = 500
    COINS_HELP_DAILY_MAX = 50
    
    async def register_bonus(self, user_id: UUID) -> CoinTransaction:
        """注册即送1000金币"""
        return await self._credit(user_id, self.COINS_REGISTER, "register")
    
    async def daily_login(self, user_id: UUID) -> CoinTransaction:
        """每日登录奖励（24h去重）"""
        if await self._has_logged_today(user_id):
            return None
        await self._debit(user_id, self.COINS_DAILY_CONSUME, "daily_consume")
        return await self._credit(user_id, self.COINS_DAILY_LOGIN, "daily_login")
    
    async def study_reward(self, user_id: UUID, minutes: int) -> CoinTransaction:
        """学习奖励（10min=1币，上限12/天）"""
        coins = min(minutes // 10, self.COINS_STUDY_DAILY_MAX - await self._today_earned(user_id, "study"))
        if coins <= 0:
            return None
        return await self._credit(user_id, coins, "study")
    
    async def trade(self, from_user: UUID, to_user: UUID, amount: int, desc: str) -> tuple:
        """用户间金币交易（ACID事务）"""
        async with db.transaction():
            from_tx = await self._debit(from_user, amount, "trade_out", to_user, desc)
            to_tx = await self._credit(to_user, amount, "trade_in", from_user, desc)
            return from_tx, to_tx
    
    async def _anti_cheat_check(self, user_id: UUID, amount: int, tx_type: str) -> bool:
        """防刷检测"""
        today_total = await self._today_earned_total(user_id)
        if today_total > 200:
            await self._flag_review(user_id, f"日收入超限: {today_total}")
            return False
        return True
```

### 2.4 MatchAgent（匹配Agent）🆕

**职责：** 跨语言用户配对

```python
class MatchAgent:
    """跨语言互助匹配引擎"""
    
    async def find_match(self, user_id: UUID) -> MatchResult:
        """为用户寻找语伴"""
        user = await self._get_user(user_id)
        
        # 1. 从Redis匹配队列查找
        match_key = f"match_queue:{user.learn_lang}:{user.native_lang}"
        candidates = await redis.zrange(match_key, 0, 9)  # 前10个候选
        
        # 2. 过滤条件
        for candidate_id in candidates:
            candidate = await self._get_user(candidate_id)
            if self._is_compatible(user, candidate):
                # 3. 匹配成功 → 从队列移除
                await redis.zrem(match_key, candidate_id)
                return MatchResult(
                    matched=True,
                    partner=candidate,
                    session=await self._create_session(user_id, candidate_id)
                )
        
        # 4. 无匹配 → 入队等待
        await redis.zadd(match_key, {str(user_id): time.time()})
        return MatchResult(matched=False, queue_position=await redis.zrank(match_key, user_id))
    
    def _is_compatible(self, a: User, b: User) -> bool:
        """匹配条件：母语互补 + 水平差≤1"""
        return (
            a.native_lang == b.learn_lang and
            b.native_lang == a.learn_lang and
            abs(CEFR_LEVELS[a.current_level] - CEFR_LEVELS[b.current_level]) <= 1
        )
```

### 2.5 LeaderboardAgent（排行榜Agent）🆕

**职责：** 每日/周/月排行榜计算和推送

```python
class LeaderboardAgent:
    """排行榜Agent"""
    
    async def compute_daily(self, date: date) -> list[LeaderboardEntry]:
        """每日00:05 Cron触发"""
        # 从CoinDailySummary计算当日Top100
        top100 = await db.execute("""
            SELECT user_id, ending_balance as coins
            FROM coin_daily_summaries
            WHERE date = :date
            ORDER BY coins DESC
            LIMIT 100
        """, {"date": date})
        
        # 写入Redis Sorted Set
        for rank, entry in enumerate(top100, 1):
            leaderboard_key = f"leaderboard:daily:{date}"
            await redis.zadd(leaderboard_key, {str(entry.user_id): entry.coins})
        
        # 推送Top3公告
        await self._announce_top3(top100[:3])
        return top100
    
    async def get_user_rank(self, user_id: UUID, period: str) -> dict:
        """获取用户排名"""
        key = f"leaderboard:{period}:{date.today()}"
        rank = await redis.zrevrank(key, str(user_id))
        score = await redis.zscore(key, str(user_id))
        total = await redis.zcard(key)
        return {"rank": rank + 1 if rank is not None else None, "coins": score, "total": total}
```

### 2.6 CompanionAgent（伴读Agent）

**变更：** 支持中/英文双模式

```python
class CompanionAgent:
    def __init__(self):
        self.scenarios = {
            "en": self._load_scenarios("en"),  # 英文场景
            "zh": self._load_scenarios("zh"),  # 🆕 中文场景
        }
        self.correction_engine = CorrectionEngine()
        self.vocab_tracker = VocabularyTracker()
    
    async def start_conversation(self, user_id: UUID, scenario_id: str, lang: str) -> Conversation:
        """启动语言对话（支持中/英文）"""
        scenario = self.scenarios[lang][scenario_id]
        return await self._run_conversation_loop(scenario, user_id, lang)
```

### 2.7 PersonaAgent / PlanAgent / KnowledgeAgent / CICDAgent

继承ELA设计，增加 `lang` 参数支持中英文。

---

## 3. 数据模型设计

### 3.1 用户系统（继承EMA + LAWA扩展）
```sql
-- ELA/EMA用户表不变
users: id, username, email, password_hash, role, tenant_id, created_at

-- LAWA用户扩展
lawa_profiles (
    id UUID PK,
    user_id UUID FK → users.id,
    native_lang VARCHAR(5) NOT NULL,        -- zh | en | fr | de
    learn_lang VARCHAR(5) NOT NULL,         -- zh | en | fr | de
    current_level VARCHAR(5),               -- A1~C2 / HSK1~6
    target_level VARCHAR(5),
    skills JSON,                            -- {"grammar": "B1", "reading": "B2", ...}
    learning_style VARCHAR(20),
    interests TEXT[],
    time_preference JSON,
    weak_areas TEXT[],
    can_help TEXT[],                        -- 🆕 我能帮别人什么 ["writing", "pronunciation"]
    total_coins INT DEFAULT 0,              -- 🆕 当前金币余额
    consecutive_login_days INT DEFAULT 0,   -- 🆕 连续登录天数
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

### 3.2 金币系统（🆕 全新）
```sql
coin_transactions (
    id UUID PK,
    user_id UUID FK → users.id,
    type VARCHAR(30) NOT NULL,       -- register | login | study | daily_consume | trade_in | trade_out | invite | reward | penalty
    amount INT NOT NULL,             -- 正=收入, 负=支出
    balance_before INT NOT NULL,
    balance_after INT NOT NULL,
    related_user_id UUID FK → users.id NULL,  -- 交易对手方
    description TEXT,
    created_at TIMESTAMP
)

coin_daily_summaries (
    id UUID PK,
    user_id UUID FK → users.id,
    summary_date DATE NOT NULL,
    coins_earned INT DEFAULT 0,
    coins_spent INT DEFAULT 0,
    net_change INT DEFAULT 0,
    ending_balance INT NOT NULL,
    study_minutes INT DEFAULT 0,
    helped_count INT DEFAULT 0,
    login_count INT DEFAULT 1,
    created_at TIMESTAMP,
    UNIQUE(user_id, summary_date)
)
```

### 3.3 互助系统（🆕 全新）
```sql
help_requests (
    id UUID PK,
    user_id UUID FK → users.id,
    lang_pair VARCHAR(10),           -- zh-en, en-zh
    content TEXT NOT NULL,           -- 求助内容
    reward_coins INT NOT NULL,       -- 悬赏金币
    status VARCHAR(10) DEFAULT 'open',  -- open | accepted | completed | cancelled
    accepted_by UUID FK → users.id NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

help_responses (
    id UUID PK,
    request_id UUID FK → help_requests.id,
    responder_id UUID FK → users.id,
    content TEXT NOT NULL,
    status VARCHAR(10) DEFAULT 'pending',  -- pending | accepted | rejected
    rating INT NULL,                 -- 1-5星评价
    created_at TIMESTAMP
)

match_sessions (
    id UUID PK,
    user_a_id UUID FK → users.id,
    user_b_id UUID FK → users.id,
    lang_pair VARCHAR(10),
    status VARCHAR(10),              -- waiting | active | ended
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    messages JSONB                   -- 实时对话记录
)
```

### 3.4 排行榜系统（🆕 全新）
```sql
leaderboard_snapshots (
    id UUID PK,
    period VARCHAR(10) NOT NULL,     -- daily | weekly | monthy
    snapshot_date DATE NOT NULL,
    rankings JSONB NOT NULL,         -- [{rank, user_id, coins}, ...]
    created_at TIMESTAMP,
    UNIQUE(period, snapshot_date)
)
```

### 3.5 评估/对话/计划（继承ELA，加lang字段）
```sql
assessments (..., lang VARCHAR(5) NOT NULL DEFAULT 'en')  -- zh | en
conversations (..., lang VARCHAR(5) NOT NULL DEFAULT 'en')
learning_plans (..., lang VARCHAR(5) NOT NULL DEFAULT 'en')
daily_tasks (..., lang VARCHAR(5) NOT NULL DEFAULT 'en')
vocabulary (..., lang VARCHAR(5) NOT NULL DEFAULT 'en')
```

### 3.6 知识库（扩展为多语言）
```sql
knowledge_chunks (
    id UUID PK,
    lang VARCHAR(5) NOT NULL,        -- zh | en | fr | de
    category VARCHAR(30),            -- grammar | vocabulary | scenario | ...
    title VARCHAR(200),
    content TEXT,
    cefr_level VARCHAR(5),
    embedding VECTOR(384),           -- ChromaDB
    created_at TIMESTAMP
)
```

---

## 4. LLM架构

### 4.1 多模型路由策略（继承EMA）
```
评估/评分类 → deepseek-v4-pro (NVIDIA API)
AI伴读对话 → deepseek-chat (性价比)
纠错/批改 → deepseek-v4-free
金币/匹配/排行 → 规则引擎(不依赖LLM)
简单任务 → ollama/llama3.2-local
```

### 4.2 关键Prompt设计（LAWA新增）

**中文评估Prompt:**
```
System: 你是HSK汉语水平评估专家。严格按照HSK标准评分。
Task: 评估以下中文写作/回答的HSK等级。
评分维度: 汉字准确性、词汇丰富度、语法正确性、表达流畅度、内容完整性
Output: 结构化JSON + HSK等级映射
```

**金币交易通知Prompt（模板化，非LLM）:**
```
🪙 +{amount} | {description} | 余额: {balance}
```

**排行榜公告:**
```
🏆 今日金币排行榜 Top 3 🥇{user1}({coins1}) 🥈{user2}({coins2}) 🥉{user3}({coins3})
你的排名: 第{rank}名 | 持有{coins}金币
```

### 4.3 LLM费用估算（LAWA版）
| 模块 | 模型 | 月调用量 | 月费 |
|------|------|---------|------|
| 水平评估(中/英) | DeepSeek-V4-Pro | 3000次 | ~¥400 |
| AI伴读对话 | DeepSeek-V4-Free | 15000次 | ~¥150 |
| 纠错/批改 | DeepSeek-V4-Free | 10000次 | ~¥80 |
| 规划生成 | DeepSeek-V4-Pro | 500次 | ~¥80 |
| **总计** | | | **~¥710/月** |

---

## 5. 项目目录结构

```
LAWA/
├── PROMPT.md                        # 项目Prompt（LAWA版）
├── PROMPT_L2.md                     # 升级指令（ELA→LAWA）
├── README.md
├── requirements.txt
├── start.sh
├── Dockerfile
├── docker-compose.yml
│
├── docs/
│   ├── 01-立项/项目章程-PROJECT-CHATER.md
│   ├── 02-可行性研究/可行性研究报告-FS.md
│   ├── 03-产品设计/PRD-产品需求文档.md
│   ├── 04-技术架构/技术架构设计文档-ARCH.md
│   ├── 05-开发计划/MVP任务拆解-SPRINT.md
│   └── 06-运营/运营计划.md
│
├── src/
│   ├── __init__.py
│   ├── main.py                      # 服务入口
│   ├── api_server.py                # FastAPI应用
│   ├── config.py                    # 配置
│   │
│   ├── agent/                       # Agent层
│   │   ├── __init__.py
│   │   ├── base_agent.py            # BaseAgent(继承EMA)
│   │   ├── main_agent.py            # LAWAOrchestrator
│   │   ├── assessment_agent.py      # 评估Agent(中/英)
│   │   ├── companion_agent.py       # 伴读Agent(中/英)
│   │   ├── plan_agent.py            # 规划Agent
│   │   ├── persona_agent.py         # 画像Agent
│   │   ├── knowledge_agent.py       # 知识库Agent
│   │   ├── coin_agent.py            # 🆕 金币Agent
│   │   ├── match_agent.py           # 🆕 匹配Agent
│   │   ├── leaderboard_agent.py     # 🆕 排行榜Agent
│   │   └── cicd_agent.py            # CI/CD Agent
│   │
│   ├── models/                      # 数据模型
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── assessment.py
│   │   ├── plan.py
│   │   ├── conversation.py
│   │   ├── vocabulary.py
│   │   ├── coin.py                  # 🆕 金币模型
│   │   ├── help.py                  # 🆕 互助模型
│   │   └── leaderboard.py           # 🆕 排行榜模型
│   │
│   ├── services/                    # 服务层
│   │   ├── __init__.py
│   │   ├── llm_service.py          # LLM调用封装
│   │   ├── cefr_mapper.py          # CEFR映射
│   │   ├── hsk_mapper.py            # 🆕 HSK映射
│   │   ├── scoring.py              # 评分引擎
│   │   ├── correction.py           # 纠错引擎
│   │   ├── vocabulary_service.py   # 词汇服务
│   │   ├── rag_service.py          # RAG检索
│   │   ├── coin_service.py         # 🆕 金币服务
│   │   ├── match_service.py        # 🆕 匹配服务
│   │   ├── leaderboard_service.py  # 🆕 排行榜服务
│   │   └── i18n_service.py         # 🆕 多语言服务
│   │
│   ├── api/                         # API路由
│   │   ├── __init__.py
│   │   ├── assessment.py           # /api/v1/assessment
│   │   ├── companion.py            # /api/v1/companion
│   │   ├── plan.py                 # /api/v1/plan
│   │   ├── vocabulary.py           # /api/v1/vocabulary
│   │   ├── profile.py              # /api/v1/profile
│   │   ├── reports.py              # /api/v1/reports
│   │   ├── coin.py                 # 🆕 /api/v1/coin
│   │   ├── help.py                 # 🆕 /api/v1/help
│   │   ├── match.py                # 🆕 /api/v1/match
│   │   └── leaderboard.py          # 🆕 /api/v1/leaderboard
│   │
│   ├── auth/                        # 用户认证（继承EMA）
│   │   ├── __init__.py
│   │   ├── jwt.py
│   │   └── dependencies.py
│   │
│   └── data/                        # 数据层
│       ├── database.py              # DB初始化
│       └── migrations/              # 数据库迁移
│
├── data/                             # 运行时数据
│   ├── user_profiles/
│   ├── knowledge_base/
│   │   ├── en/                      # 英文知识库
│   │   ├── zh/                      # 🆕 中文知识库
│   │   ├── fr/                      # 🆕 法文预留
│   │   └── de/                      # 🆕 德文预留
│   └── test_banks/
│       ├── en/                      # 英文题库
│       └── zh/                      # 🆕 中文题库
│
├── ui/                              # 前端
│   └── ...
│
└── tests/                           # 测试
    ├── test_assessment.py
    ├── test_companion.py
    ├── test_cefr.py
    ├── test_hsk.py                   # 🆕
    ├── test_coin.py                  # 🆕
    ├── test_match.py                 # 🆕
    └── test_leaderboard.py           # 🆕
```

---

## 6. 非功能设计

### 6.1 性能指标
| 指标 | 目标 | 方案 |
|------|------|------|
| API响应(P95) | <500ms(非LLM), <3s(LLM流式首Token) | Redis缓存 + 异步 + 流式 |
| 金币事务 | ACID保证，零双花 | SQLite事务 + 乐观锁 |
| 排行榜读取 | <100ms | Redis Sorted Set |
| 匹配延迟 | <5s(有候选) / 入队(无候选) | Redis队列 |
| 并发 | 100+ | FastAPI异步 + 连接池 |

### 6.2 安全设计
| 方面 | 方案 |
|------|------|
| 认证 | JWT (HS256, 24h过期) |
| 密码 | bcrypt哈希 |
| 金币事务 | 乐观锁 + 唯一约束防并发 |
| 防刷 | 日上限 + 异常标记 + 人工审核 |
| CORS | 白名单控制 |
| 数据加密 | AES-256 GCM |
| API限流 | Redis Token Bucket(60rpm/user) |

---

## 7. 技术选型汇总

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **后端框架** | FastAPI | >=0.110 | API服务 |
| **运行环境** | Python | 3.11+ | 后端 |
| **ORM** | SQLAlchemy 2.0 | >=2.0 | 数据库ORM |
| **数据库** | SQLite/PostgreSQL | — | 数据存储+金币事务 |
| **缓存/队列** | Redis | >=7.0 | 缓存/会话/排行榜/匹配队列 |
| **向量DB** | ChromaDB | >=0.5 | 知识库向量 |
| **前端** | Vue 3 + Vite + TS | — | UI |
| **i18n** | Vue I18n | >=9 | 多语言界面 |
| **实时通信** | WebSocket + Redis Pub/Sub | — | 实时匹配+聊天 |
| **LLM** | NVIDIA API/DeepSeek/Ollama | — | 推理 |
| **ASR** | Whisper | — | 语音转文字 |
| **TTS** | edge-tts / Fish-Speech | — | 语音合成 |
| **认证** | PyJWT + passlib | — | 用户认证 |
| **HTTP** | httpx | >=0.27 | LLM异步请求 |

---

> 📝 **文档变更记录**
> | 版本 | 日期 | 变更内容 | 作者 |
> |------|------|---------|------|
> | v1.0 (ELA) | 2026-05-27 | ELA技术架构初稿 | GDP影子 |
> | v1.0 (LAWA) | 2026-05-27 | 升级：新增CoinAgent/MatchAgent/LeaderboardAgent + 多语言 + WebSocket | GDP影子 |
