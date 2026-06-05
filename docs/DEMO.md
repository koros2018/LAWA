# 🎬 LAWA 用户试用指南

## 快速开始（3分钟）

```bash
# 1. 生成演示数据
python3 scripts/seed.py

# 2. 启动服务
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 6288 --reload

# 3. 打开浏览器
# API 文档: http://localhost:6288/docs
# 前端: http://localhost:6289 （需单独启动前端）
```

## 演示账户

| 用户名 | 密码 | 母语→学习 | 等级 | 金币 |
|--------|------|-----------|------|------|
| alice | demo123 | 中文→English | B1 | 2500 |
| bob | demo123 | English→中文 | HSK2 | 1800 |
| carol | demo123 | 中文→Français | A2 | 3200 |

## 登录测试

```bash
# Alice 登录
curl -X POST http://localhost:6288/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"demo123"}'

# 返回: {"access_token":"eyJ...", "token_type":"bearer", "user_id":"..."}
```

## 核心功能试用路径

### 1. 评估流程
```
POST /api/v1/assessment/start     → 开始评估
POST /api/v1/assessment/question   → 获取题目
POST /api/v1/assessment/answer     → 提交答案
POST /api/v1/assessment/report     → 获取报告
GET  /api/v1/assessment/history/{user_id} → 历史记录
```

### 2. 任务市场
```
GET  /api/v1/tasks                 → 浏览任务（已有5个演示任务）
POST /api/v1/tasks/{task_id}/accept → 接任务
POST /api/v1/tasks/{task_id}/submit → 提交任务
POST /api/v1/tasks/{task_id}/review → 评价任务
```

### 3. 金币系统
```
GET  /api/v1/coin/balance/{user_id} → 查余额
GET  /api/v1/coin/transactions/{user_id} → 交易记录
POST /api/v1/coin/trade             → 金币交易
```

### 4. 社区引擎
```
GET  /api/v1/community/leaderboard/coins → 金币排行榜
GET  /api/v1/community/leaderboard/study → 学习排行榜
POST /api/v1/community/match/find        → 找语言伙伴
POST /api/v1/community/help/post         → 发求助帖
```

### 5. AI 伴读
```
GET  /api/v1/companion/scenarios        → 查看场景列表
POST /api/v1/companion/session/start    → 开始伴读
POST /api/v1/companion/session/message  → 发送消息（含AI纠错）
POST /api/v1/companion/correct          → 语法纠错
```

### 6. AI 导师
```
GET  /api/v1/tutor/profile              → 导师画像
POST /api/v1/tutor/evolve               → 进化导师
GET  /api/v1/tutor/lesson               → 生成微课件
GET  /api/v1/tutor/insights             → 学习洞见
GET  /api/v1/tutor/market               → 导师市场
```

## 运行测试

```bash
# 全量测试（68个）
python3 -m pytest tests/ -v

# 仅单元测试
python3 -m pytest tests/test_security.py tests/test_config.py tests/test_level_mapper.py -v

# 仅集成测试
python3 -m pytest tests/test_api.py tests/test_models.py tests/test_assessment.py -v
```

## 技术架构速览

```
用户请求 → FastAPI Route → Agent (业务逻辑) → LLM Service → Provider
                ↕
           SQLAlchemy ORM → SQLite / PostgreSQL
```

- **56 个 API 端点**
- **12 个 Agent** 处理业务逻辑
- **3 个 LLM Provider**: NVIDIA NIM / OpenCode / Ollama
- **7 个数据表**: users, lawa_profiles, assessments, tasks, coin_transactions, companion_sessions, tutor_profiles

## 已知限制

- LLM 调用依赖外部 API（NVIDIA/OpenCode），需要有效 API Key
- Ollama 本地兜底需要单独安装运行
- 部分 Agent 功能（persona 增量更新、plan 动态调整）返回 stub
- WebSocket 实时通信尚未实现
- Redis 缓存层为可选组件

## 环境变量

复制 `.env.example` → `.env`，主要配置：
- `LLM_NVIDIA_KEY` — NVIDIA NIM API Key（主要）
- `LLM_OPENCODE_KEY` — OpenCode API Key（备用）
- `JWT_SECRET` — JWT 签名密钥（生产环境必须修改）
- `DB_USE_SQLITE=true` — 开发模式用 SQLite
