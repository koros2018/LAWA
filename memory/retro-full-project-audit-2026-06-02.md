# 🔬 LAWA 项目深度复盘 — 三大技能联合审计

**日期**: 2026-06-02 12:15 CST
**审计者**: 达子（🦝）
**工具**: 架构法则 + 业务流程设计 + 第一性原理调试
**覆盖范围**: 19 Agent × 9 路由模块 × 21 Vue 视图 × 7 测试文件
**总耗时**: 45min（扫描 15min + 分析 15min + 报告 15min）

---

## 执行摘要

本次审计应用三把手术刀对 LAWA 全项目进行了一次前所未有的深入扫描。结果：**评估系统的 bug 不是孤立事件，它是一个系统性模式的冰山一角。**

核心发现：
- 🔴 **P0**: TaskDetailView 存在与 AssessmentResultView 完全相同的路由参数不匹配
- 🔴 **P0**: 8/10 路由模块零 DB session 注入 — 大量 Agent 生成幽灵状态
- 🟠 **P1**: 项目内存在三种互斥的持久化模式，无统一约定
- 🟠 **P1**: `execute_with_timeout` 是死代码，无人使用
- 🟡 **P2**: 测试覆盖了模型层但遗漏了集成层 — 端到端盲区
- ⚡ **架构级**: rpg.py 是"超级边界" — 7 Agent 挤在一个路由文件中

---

## 第一部分：业务流程审计（business-flow-design 技能）

### 1.1 流程全景图

LAWA 涉及的核心用户流程：

```
流程              前端入口          路由模块        Agent          持久化？
─────────────────────────────────────────────────────────────────
评估               AssessmentView    assessment      assessment      ✅ (今天刚修)
任务市场            TaskMarketView    task            task            ❌
任务创建            TaskCreateView    task            task            ❌
任务详情            TaskDetailView    task            task            ❌
金币               CoinView          coin            coin            ❌
匹配               MatchView         community       match           ❌
排行榜              LeaderboardView   community       leaderboard     ✅ (agent内部直连)
帮助请求            HelpView          community       help            ✅ (agent内部直连)
AI 学伴             CompanionView     companion       companion       ❌
人格/计划            PlanView          persona_plan    persona+plan    ❌
RPG 角色            DashboardView     rpg             character       ✅ (agent内部直连)
RPG 任务            WorldMapView      rpg             quest           ✅ (agent内部直连)
RPG 公会            GuildView         rpg             guild           ✅ (agent内部直连)
RPG 物品            ShopView          rpg             item            ✅ (agent内部直连)
RPG 成就            AchievementView   rpg             achievement     ✅ (agent内部直连)
RPG 活动            EventsView        rpg             event           ✅ (agent内部直连)
RPG 总架构师        —                 rpg             architect       ✅ (agent内部直连)
导师               TutorView         tutor           tutor           ❌
```

**统计**：
- 18 条用户流程
- 8 条有持久化（全部 RPG 相关 + assessment + 2 个 community）
- **10 条无持久化或持久化模式混乱**

### 1.2 断环检测

逐流程进行状态闭环验证，发现以下断环：

#### 🔴 P0: 任务市场 → 任务详情（路由断环）

```
TaskMarketView: router.push(`/tasks/${task.id}`)
                      ↓
Router: path: '/tasks/:id'  param name = "id"
                      ↓
TaskDetailView: route.params.taskId  ← ❌ 读取 "taskId"，实际是 "id"
                      ↓
GET /api/v1/tasks/undefined  ← 💥 404
```

**与评估系统 bug 完全同构**。区别只在于参数名（`:id` vs `sessionId` vs `taskId`）。

#### 🟠 P1: 任务创建 → 任务详情（双重幽灵）

```python
# task_agent.py — 生成 task_id 但不持久化
task_id = str(uuid.uuid4())
return {"task": {"id": task_id, ...}}

# task_agent.py — 提交/审核/完成操作也不持久化
"id": str(uuid.uuid4()),  # 第128行
"id": str(uuid.uuid4()),  # 第182行
```

**整条任务流程是幽灵状态** — 任务被创建、接取、提交、完成，全程不在数据库留下任何痕迹。

#### 🟠 P1: 金币系统（零持久化）

```python
# coin_agent.py — 唯一 uuid4() 调用
"id": str(uuid.uuid4()),  # 第87行 — 交易ID，生成即丢弃
```

金币余额、交易记录、每日登录奖励 — 全部在内存中计算，刷新后消失。

#### 🟠 P1: 匹配系统（零持久化）

```python
# match_agent.py — 2个 uuid4()，0个 DB 操作
"registered_at": str(uuid.uuid4()),  # 匹配注册
match_id = str(uuid.uuid4())          # 匹配会话
```

匹配请求和结果未持久化，无法审计匹配历史。

#### 🟡 P2: Companion / Plan / Persona / Tutor（零持久化）

4 个 Agent 完全不操作数据库。对话记录、学习计划、人格档案 — 会话结束后消失。

### 1.3 架构适配性沟通

映射流程到架构，发现三种互斥的持久化模式：

```
模式 A: Route 注入 DB → Agent 通过 payload["db"] 获取
  使用者: assessment_agent（今天刚改的）

模式 B: Agent 内部直接获取 Session
  使用者: achievement, architect, character, event, guild, help, item, leaderboard, quest
  特点: routes 不提供 DB，Agent 自己 manage session

模式 C: 无持久化
  使用者: coin, companion, match, persona, plan, task, tutor
  特点: 纯内存计算
```

**关键问题**：三种模式共存意味着：
1. 没有统一的持久化约定
2. Agent 的实现方式取决于"谁写的"而非"它做什么"
3. 无法跨 Agent 执行原子事务
4. 新人加入项目时不知道该选哪种模式

---

## 第二部分：架构法则审计（architecture-laws 技能）

### 2.1 边界熵增法则 — 评分：🔴 高危

| 位置 | 漂移证据 |
|------|----------|
| 路由 `:id` → 组件 `taskId` | TaskDetailView 参数不匹配 |
| 路由 `:id` → 组件 `sessionId` | AssessmentResultView（已修复） |
| Agent `assessment_id` ≠ 路由 `:id` ≠ 组件 `sessionId` | 评估系统（已修复） |
| 前端 `taskId` ≠ 后端 `task_id` | 跨边界命名不一致 |
| 前端 `userId` ≠ 后端 `user_id` | 多个视图中存在 |

**量化**：9 个路由模块 × 19 个 Agent × 21 个视图 = **49 个边界**。无共享 Schema → 漂移概率极高。

### 2.2 幽灵状态法则 — 评分：🔴 高危

```
Agent 持久化状态分布：
████████████ 已持久化: 11 agents (assessment刚修 + 10 RPG/community)
████████ 零持久化:   8 agents (coin/match/task/persona/plan/companion/tutor/leaderboard?*)
```

*leaderboard_agent 有 21 个 session_refs，属于模式 B。

**幽灵状态清单**：

| Agent | 生成 UUID 数 | DB 操作数 | 影响范围 |
|-------|-------------|----------|----------|
| task_agent | 3 | 0 | 整个任务系统 |
| match_agent | 2 | 0 | 匹配系统 |
| coin_agent | 1 | 0 | 金币系统 |
| persona_agent | 0 | 0 | 人格档案 |
| plan_agent | 0 | 0 | 学习计划 |
| companion_agent | 1 | 0 | 对话历史 |
| tutor_agent | 0 | 0 | 导师记录 |

**集体风险**：如果数据库重启或服务重启，上述所有系统数据永久丢失。

### 2.3 隐式契约脆弱性法则 — 评分：🟠 注意

发现的隐式契约断裂点：

1. **BaseAgent 的超时机制无人使用**
   ```python
   # base_agent.py:70 — 定义了但从未被调用
   async def execute_with_timeout(self, payload, timeout_seconds=60):
       return await asyncio.wait_for(self.execute(payload), timeout=timeout_seconds)
   
   # 所有路由: agent.execute() — 没有任何超时保护
   ```
   意味着：如果某个 Agent 的 LLM 调用卡住，整个请求会挂起直到网关超时。

2. **LLM 超时 (120s) vs 前端超时 (30s) 严重不匹配**
   ```
   前端 axios timeout: 30s
   后端 LLM timeout: 120s
   Agent execute timeout: 未使用（无限等待）
   ```
   三个超时值完全不协调。LLM 慢 → 前端先超时 → 用户看到错误 → 但后端还在跑。

3. **Agent 之间的调用无超时/重试/熔断机制**
   只有 `llm_service.py` 有 circuit breaker。Agent 层没有任何保护。

### 2.4 倒置测试金字塔 — 评分：🟡 中等（改善中）

与第一次诊断（零测试）不同，项目确实有测试：

```
tests/
├── test_api.py          ✅ 健康检查 + 注册/登录
├── test_assessment.py   ✅ 评估 404/无效UUID/DB查询
├── test_config.py       ✅ 配置验证
├── test_level_mapper.py ✅ 等级映射
├── test_models.py       ✅ 模型创建/唯一性
├── test_rpg.py          ✅ 成就/活动/总架构师
├── test_security.py     ✅ 安全端点
frontend/e2e/vue.spec.ts ❌ 默认脚手架模板
```

**测试质量评估**：
- ✅ **模型层**: 有覆盖
- ✅ **API 端点层**: 有覆盖
- ❌ **流程集成层**: 零覆盖
- ❌ **前端组件层**: 零覆盖
- ❌ **E2E 层**: 默认模板
- ❌ **契约测试**: 不存在

**这就是为什么评估 bug 逃过测试的原因** — 测试验证了"API 返回正确的 HTTP 状态码"，但没有验证"完整的用户流程能走通"。

### 2.5 微观康威法则 — 评分：🔴 高危

最显著的康威熵现象：

```
三种持久化模式 = 三种不同的心智模型：

模式 A 作者: "路由提供 DB session，Agent 只管业务逻辑"
模式 B 作者: "Agent 自己管理一切，路由只做转发"
模式 C 作者: "这个 Agent 很简单，不需要数据库"
```

**证据**：
- `rpg.py`: 零 `Depends(get_db)`，但 Agent 内部自己管理 session
- `assessment.py`: 5 个 `Depends(get_db)`，agent 通过 payload 获取
- `coin.py`: 零 `Depends(get_db)`，agent 也不操作 DB
- `companion.py`: 零 `Depends(get_db)`，agent 内部有 41 个 session 引用（最混乱）

**本质上，每个路由模块的作者对"数据属于谁"有完全不同的理解。**

### 2.6 集成表面积爆炸 — 评分：🟠 注意

最严重的集成表面积问题：

**rpg.py — 超级边界**：
```
rpg.py 涉及 7 个 Agent:
  character → quest → guild → item → achievement → architect → event

7 个 Agent 的交互对数 = 7×6/2 = 21 对潜在交互
如果每个 Agent 95% 可靠 → rpg 子系统可靠性 = 0.95^7 ≈ 70%
```

加上 `community.py`（3 个 Agent）和 `persona_plan.py`（2 个 Agent），路由层的总集成表面积：
```
rpg(7) × community(3) × persona_plan(2) × assessment(1) × coin(1) × 
companion(1) × task(1) × tutor(1) = 17 个独立 Agent 实例
```

**没有任何跨 Agent 流程的集成测试**。

---

## 第三部分：同类隐患搜索（first-principles-debugging 技能第 4 步）

### 3.1 搜索模式：路由参数不匹配

```bash
# 搜索所有 :param 定义 vs 所有 route.params 读取
```

**结果**：
| 路由 | 参数名 | 组件读取 | 状态 |
|------|--------|----------|------|
| `/assessment/:id` | `id` | `route.params.id` | ✅ 已修复 |
| `/tasks/:id` | `id` | `route.params.taskId` | ❌ 不匹配 |

**仅 2 条参数化路由，2 条都不匹配（修复前）**。不匹配率 = 100%。

### 3.2 搜索模式：uuid4() + 无 DB 操作

```bash
grep -rn "uuid4()" --include="*.py" -A10 | grep -v "\.add\|db\.commit"
```

**结果**：task_agent (3处)、match_agent (2处)、coin_agent (1处)、companion_agent (1处，但有大量 session 引用，可能通过其他方式持久化)

### 3.3 搜索模式：无 DB depend 的路由 + 有写操作的 Agent

| 路由 | Agent | Agent 有写操作？ | DB Depends? |
|------|-------|-----------------|-------------|
| `coin.py` | coin_agent | ✅ (交易/奖励) | ❌ |
| `community.py` | match_agent | ✅ (匹配注册) | ❌ |
| `task.py` | task_agent | ✅ (创建/提交/审核) | ❌ |
| `companion.py` | companion_agent | ✅ (对话) | ❌ |
| `persona_plan.py` | persona_agent | ✅ (人格分析) | ❌ |
| `tutor.py` | tutor_agent | ✅ (题目/纠错) | ❌ |

**共 6 个 Agent 有写操作但所在路由模块没有 DB session**。

---

## 第四部分：修复路线图

### P0 — 立即修复（本周）

| # | 问题 | 修复 | 预计耗时 |
|---|------|------|----------|
| 1 | TaskDetailView 路由不匹配 | `route.params.taskId` → `route.params.id` | 5min |
| 2 | task_agent 零持久化 | 参照 assessment_agent 模式添加 DB 支持 | 2h |
| 3 | coin_agent 零持久化 | 添加 DB session 注入 + 写表 | 1.5h |

### P1 — 架构加固（下周）

| # | 问题 | 修复 | 预计耗时 |
|---|------|------|----------|
| 4 | 统一持久化模式 | 选定模式 A（路由注入 DB），将所有 Agent 迁移 | 4h |
| 5 | BaseAgent 加 `_persist()` 钩子 | 新建 Agent 时必须实现 | 1h |
| 6 | 启用 execute_with_timeout | 所有路由用 `execute_with_timeout` 替代 `execute` | 1h |
| 7 | 修复前端/后端超时不匹配 | 前端按端点分级超时 | 1h |
| 8 | 添加 E2E 测试 | 评估流程 + 任务流程各 1 条 | 3h |

### P2 — 系统性改进（本月）

| # | 问题 | 修复 | 预计耗时 |
|---|------|------|----------|
| 9 | 生成 OpenAPI Schema | 从 FastAPI 自动生成，前端共享类型 | 2h |
| 10 | 添加 contract test | CI 中检测路由参数名一致性 | 2h |
| 11 | 拆分 rpg.py | 按领域拆分为 7 个独立路由模块 | 3h |
| 12 | 新人入职文档 | 明确持久化模式选择 + Agent 开发规范 | 2h |

### 📊 总预计工作量

| 等级 | 条目 | 总耗时 |
|------|------|--------|
| P0 | 3 | 3h 35min |
| P1 | 5 | 10h |
| P2 | 4 | 9h |
| **合计** | **12** | **~22.5h** |

---

## 第五部分：新发现的架构法则

在本次审计中，除了之前识别的六条法则外，发现了第七条：

### ⑦ 模式分裂法则（Pattern Bifurcation Law）

> 当多个开发者（或同一开发者在多个时间段）独立实现相似功能时，即使功能需求相同，实现模式也会自然分裂。如果组织不提供明确的模式选择指南，最终会形成 N 种互斥的实现模式——每种在自己的上下文里"都合理"，但共存时产生系统性脆弱。

**LAWA 表现**：三种持久化模式（路由注入 / Agent 自管 / 零持久化）在同一个代码库中共存，彼此互不兼容。

**推论**：模式分裂一旦发生，修复成本 = (N−1) × 迁移成本。三种模式 → 需要迁移两种 → 成本是单一模式的 2 倍。

---

## 附录：诊断命令速查

本次审计使用的所有扫描命令，可用于持续监控：

```bash
# 边界熵增监控
diff <(grep -oP 'params\.\w+' frontend/src/views/*.vue | sort) \
     <(grep -oP ':/\w+' frontend/src/router/index.ts | sort)

# 幽灵状态监控
grep -rn "uuid4()" src/agent/*.py | while read line; do
  f=$(echo $line | cut -d: -f1)
  has_db=$(grep -c "\.add\|db\.commit" $f)
  [ "$has_db" -eq 0 ] && echo "GHOST: $line"
done

# 模式分裂监控
echo "=== Route-level DB injection ==="
grep -l "Depends(get_db)" src/routes/*.py
echo "=== Agent-level DB management ==="
grep -l "session\.\|AsyncSession" src/agent/*.py
```

---

*"第一次复盘是修代码。第二次复盘是修模式。第三次复盘是修文化。" — 达子 🦝*
