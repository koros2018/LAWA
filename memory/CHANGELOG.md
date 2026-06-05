# LAWA 变更日志

## 2026-06-02 — Bugfix: 评估系统 Result Not Found

### 修复的 Bug
- 🐛 **P1 阻断**: 评估完成后页面显示 "result_not_found"，无法查看结果
  - 根因 1: 三重路由/API不匹配（前端跳转/路由参数/后端路径全对不上）
  - 根因 2: 评估数据从未持久化到 DB（start_assessment 只生成 UUID 不写库）
  - 根因 3: writing 维度题目 LLM 生成超 30s，触发 axios timeout
  - 修复: 4文件改动 — 路由对齐 + localStorage 兜底 + DB 持久化 + 超时提至 60s
  - 浅层报告: [retro-assessment-bugfix-2026-06-02.md](retro-assessment-bugfix-2026-06-02.md)
  - 🧠 深层复盘 (6大架构法则): [retro-deep-assessment-bugfix-2026-06-02.md](retro-deep-assessment-bugfix-2026-06-02.md)
  - 🔬 全项目审计 (3技能联合 + 12条修复路线): [retro-full-project-audit-2026-06-02.md](retro-full-project-audit-2026-06-02.md)
    - 🔴 P0: TaskDetailView 同款路由bug / 8路由零DB注入 / 6 Agent全幽灵状态
    - 🟠 P1: 3种互斥持久化模式 / execute_with_timeout死代码
    - 🆕 发现第7条法则: 模式分裂法则

## 2026-05-31 — Day 3 & Day 4 (RPG 世界系统 Phase 2)

### Day 3: API 路由 + 前端
- ✅ RPG API 全端点: 14 路由 (角色8+世界4+任务6+旅行1)
- ✅ Dashboard RPG 面板: XP条/等级/职业/称号
- ✅ 世界地图页面: 2区10场景可视化
- ✅ 端到端联调: 全部18端点实测通过

### Day 4: 公会系统 + 监督员
- ✅ GuildModel: 3表 (language_guilds/guild_members/guild_tasks)
- ✅ GuildAgent: 10 action (list/my/create/join/leave/detail/contribute/tasks/task_progress)
- ✅ Guild API: 9端点 (/api/v1/rpg/guild*)
- ✅ 种子数据: 3公会 6成员 5任务
- ✅ 前端公会页面: GuildView.vue + Dashboard入口
- ✅ 监督员 v2.0: 独立守护进程 + LLM透测 + 会话锁死检测
- ✅ 数据表: 11→28, Agent: 12→15, 端点: 56→83+
- ✅ 68测试零回归

### 已修复的 Bug
- 路由顺序冲突 (`/character/classes` 被 `/{user_id}` 吞掉)
- 旧表缺列 (lawa_profiles 缺 RPG 8列，手动 ALTER TABLE 补齐)
- 时区比较 (naive-aware datetime 在 quest complete 时炸掉)
- 多公会兼容 (Alice 2个公会导致 scalar_one_or_none 报错)
- 缩进错误 (edit 操作导致 quest_agent.py 语法错误)

## 2026-05-27

### 项目启动
- **15:00** Ke 创建 LAWA 项目文档体系（章程/可行性/PRD/架构/Sprint）
- **17:20** Ke 与 达子 首次项目对齐
- 达子正式接替"GDP影子"，成为项目文档作者
- 确定三条核心规则：
  1. 优先"方案A+B融合"，朝"方案C（Duolingo遇见魔兽世界）"前进
  2. 每日进展汇报、里程碑复盘、全部记录存档
  3. 代码稳定后Git版本管理

### 关键决策
| 决策 | 内容 | 决策人 |
|------|------|--------|
| D-001 | Sprint计划v2.0：融合A+B，朝向C，8个Sprint/16周 | Ke + 达子 |
| D-002 | 数据库选型：PostgreSQL一步到位（非SQLite） | Ke |
| D-003 | 达子替换GDP影子，作为项目文档作者 | Ke |
| D-004 | 项目日志体系建立（daily + milestones + changelog） | Ke + 达子 |

### 升级方向确认
- ✅ 方案A（Real Task Marketplace）→ Sprint 6
- ✅ 方案B（AI Tutor Personalization + Federated Learning）→ Sprint 8
- ✅ 方案C（Language World RPG）→ 北极星目标，各Sprint预留架构钩子

---

## Sprint 9: AI灵魂导师 (Soul Tutor) — 2026-06-02

### 🎯 目标
为 LAWA 打造"Duolingo 遇见 魔兽世界"中的灵魂角色：1v1 AI伴读导师

### ✅ 已完成

**数据模型** (`src/models/tutor.py`)
- `TutorPersona` — 导师人格表（唯一导师名/风格/幽默/声音/专长）
- `TutorConversation` — 对话历史表（用户↔导师完整对话记录）
- `TutorMemoryNote` — 导师记忆表（用户特点/偏好/弱点，重要性+召回计数）

**TutorAgent 七大能力** (`src/agent/tutor_agent.py`)
1. `onboard` — 新用户入驻，随机生成独一无二的导师人格（12个中+12个英名字池×5幽默风格×5声音×5教学风格 = 数千种组合）
2. `chat` — 核心1v1对话，注入完整人格prompt、对话历史、导师记忆
3. `adjust` — 难度调整（easier/harder），更新DB+写入记忆
4. `history` — 对话历史查询
5. `check_in` — 主动关怀（随机选择问候语）
6. `evolve/lesson/insights` — 保留原有进化+课件+洞见功能
7. `list_public/rent` — 导师市场（保留）

**API 路由** (`src/routes/tutor.py`) — 12个端点
- POST /tutor/onboard, /tutor/chat, /tutor/adjust, /tutor/check-in
- GET /tutor/history, /tutor/profile, /tutor/lesson, /tutor/insights, /tutor/market
- POST /tutor/evolve, /tutor/lesson/feedback, /tutor/rent

**基础设施**
- 全部路由注入 `db: AsyncSession`
- `src.main.py` 添加 `tutor_router` + `import src.models`
- 运行时验证全量通过（AST ✅ / import ✅ / Vite build ✅）

### 📊 导师系统规模
- 导师人格组合: 24个名字 × 5种幽默 × 5种声音 × 5种教学风格 = 3,000+ 种独特导师
- 每个导师完全随机，用户永远拿到独一无二的AI导师
- 导师记忆随学习推进不断积累，形成真正的"了解你的老师"
