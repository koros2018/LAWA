# 🦝 LAWA — Languages Are Worlds Agent

> 语言即世界 — 通过真实任务和 AI 伴读学习语言

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.5-brightgreen)](https://vuejs.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**LAWA** 是一个开源语言学习平台，结合 AI 深度参与和社区驱动的经济系统，让语言学习变得像玩游戏一样上瘾。

---

## 🧭 核心理念

| 理念 | 说明 |
|------|------|
| 🤖 **AI 无处不在** | 评估、伴读、纠错、规划 — AI 深度参与每个环节 |
| 🪙 **金币经济** | 学习即挖矿，完成真实任务赚金币，用金币求助/租导师 |
| 🌍 **真实任务** | 翻译、润色、对话练习 — 不是做题，是做真事 |
| 🧑‍🤝‍🧑 **社区驱动** | 排行榜、语言配对、互助、导师市场 |

---

## ✨ 功能矩阵

### 🏗 基础设施 (M0)
- JWT 认证 + 用户系统
- PostgreSQL + Redis + ChromaDB
- 多 LLM Provider (NVIDIA NIM / OpenCode / Ollama 本地兜底)

### 📊 评估与画像 (M1-M2)
- 中/英文自适应水平测试（语法/阅读/写作）
- VARK 学习风格识别
- 个性化学习计划（周+日）

### 🪙 金币经济 (M3)
- 注册奖励 / 每日登录 / 学习计时挖矿
- 任务悬赏 / 互助赚币 / 导师租用
- 反作弊 + 每日上限

### 💬 AI 伴读 (M4)
- 10 个场景 × 2 语言（中/英）角色扮演
- 实时语法纠错 + 文化提示
- SM-2 间隔复习算法
- 上下文窗口管理（最近15轮）

### 🎨 前端 MVP (M5)
- Vue3 + TypeScript + Vite + Pinia + Router + i18n
- 17 个视图：登录 → 评估 → 学习 → 社区 → 导师
- 中英双语 UI（60+ 翻译键）

### 📋 任务市场 (M6)
- 发布/接单/提交/验收 + 评价体系
- AI 辅助生成初稿（翻译/润色/摘要）
- 多维度筛选（类型/难度/语言对/状态）

### 🌐 社区引擎 (M7)
- **排行榜**: 金币/学习时长/互助/任务 四榜，日/周/总榜
- **语言匹配**: 母语互补配对算法
- **互助系统**: 发帖求助 + 悬赏金币 + 回答/采纳

### 🧠 AI 导师进化 (M8)
- LLM + 本地规则双重进化引擎
- 个性化微课件（5段式：热身→讲解→练习→挑战→词汇）
- 学习洞见分析 + SVG 效率仪表盘
- 导师市场（出租/租用）

---

## 📊 代码规模

| 层 | 文件数 | 代码量 | 说明 |
|-----|-------|--------|------|
| Agent | 12 | ~2200 行 | 核心业务逻辑 |
| Route | 9 | ~1800 行 | 45+ API 端点 |
| Service | 4 | ~800 行 | LLM/纠错/词汇/等级 |
| Model | 8 | ~700 行 | ORM 数据模型 + 兼容层 |
| Config/DB/Utils | 5 | ~400 行 | 基础设施 |
| Tests | 6 | ~500 行 | pytest-asyncio (61 tests) |
| **Python 合计** | **44** | **~7000 行** | |
| Vue Views | 17 | ~2400 行 | UI 组件 |
| TypeScript | 3 | ~300 行 | API + Router + i18n |
| **Frontend 合计** | **20** | **~2700 行** | |
| **总计** | **57** | **~9200 行** | |

---

## 🚀 快速启动

### 前置条件
- Python 3.12+
- Node.js 22+
- PostgreSQL 16+
- Redis 7+

### 本地开发

```bash
# 0. 前置
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 1. 数据库迁移（首次）
alembic upgrade head

# 2. 后端
cp .env.example .env    # 编辑 .env 填入 API Key
python -m src.main       # → http://localhost:6288

# 3. 前端  
cd frontend
npm run dev              # → http://localhost:6289

# 4. 测试
python -m pytest tests/ -v   # 61 tests ✓
```

### Docker 部署

```bash
# 全栈启动（含 DB + Redis + Backend + Frontend）
docker-compose up -d

# 含本地 LLM（Ollama）
docker-compose --profile local-llm up -d

# 前端 → http://localhost:6289
# 后端 → http://localhost:6288
# API 文档 → http://localhost:6288/docs
```

---

## 🗂 项目结构

```
LAWA/
├── src/                     # Python 后端
│   ├── agent/              # 12 个 Agent（业务逻辑）
│   │   ├── base_agent.py
│   │   ├── assessment_agent.py
│   │   ├── persona_agent.py
│   │   ├── coin_agent.py
│   │   ├── companion_agent.py
│   │   ├── plan_agent.py
│   │   ├── task_agent.py
│   │   ├── leaderboard_agent.py
│   │   ├── match_agent.py
│   │   ├── help_agent.py
│   │   └── tutor_agent.py
│   ├── routes/             # 9 个路由模块（45+ 端点）
│   ├── services/           # LLM / 纠错 / 词汇 / 等级映射
│   ├── models/             # SQLAlchemy ORM（7 个数据表）
│   ├── data/               # 场景库 JSON（中/英各10个场景）
│   ├── config.py           # Pydantic Settings
│   └── main.py             # FastAPI 入口
├── frontend/               # Vue3 前端
│   ├── src/views/          # 17 个视图组件
│   ├── src/router/         # 路由 + 导航守卫
│   ├── src/api/            # Axios 封装 + JWT 拦截
│   └── src/i18n/           # 中/英翻译
├── docker-compose.yml      # 全栈部署编排
├── Dockerfile              # 后端镜像
├── requirements.txt        # Python 依赖
└── README.md
```

---

## 🔌 API 速览

| 模块 | Prefix | 端点数 | 主要功能 |
|------|--------|--------|----------|
| Auth | `/api/v1/auth` | 3 | 注册/登录/个人信息 |
| Assessment | `/api/v1/assessment` | 5 | 水平测试 + 报告 |
| Persona/Plan | `/api/v1` | 4 | 画像分析 + 学习计划 |
| Companion | `/api/v1/companion` | 7 | AI伴读 + 纠错 |
| Coin | `/api/v1/coin` | 7 | 金币系统 + 交易 |
| Tasks | `/api/v1/tasks` | 8 | 任务市场 CRUD |
| Community | `/api/v1/community` | 11 | 排行榜/配对/互助 |
| Tutor | `/api/v1/tutor` | 7 | 导师进化/课件/市场 |

---

## 🤖 LLM 配置

当前活跃提供商：

| Provider | 模型 | 用途 |
|----------|------|------|
| NVIDIA NIM | deepseek-ai/deepseek-v4-pro | 评估 / 对话 / 纠错 |
| OpenCode | deepseek-v4-pro | 规划 / 课件生成 |
| Ollama | llama3.2 | 本地兜底 |

配置方式：编辑 `.env` 文件或设置环境变量。

---

## 📐 架构原则

1. **Agent 模式** — 每个业务域一个 Agent，统一 `execute(payload) → result` 接口
2. **本地兜底** — LLM 不可用时自动降级到规则引擎，确保服务不中断
3. **多 Provider 路由** — 任务类型 → Provider 映射 + 自动故障转移
4. **金币闭环** — 学习赚币 → 消费（任务/互助/导师）→ 激励学习

---

## 📜 许可

MIT License — 开源社区驱动，非商业项目。

---

*Built with 🦝 by Ke & 达子 — Sprint 0-8 completed.*
