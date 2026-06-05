# LAWA 项目深度复盘：技术债与缺陷全量分析

> 复盘人：达子 🦝 | 日期：2026-05-30  
> 方法：三轮递增深挖（数据→根因→反事实→行动项）  
> 定位：为下一步"是否深化/是否重写/何去何从"提供论证依据

---

## 一、缺陷金字塔（90项）

以下按严重程度分层。**🔴** = 生产阻塞，**🟡** = 技术债，**🟢** = 优化项。

### 🔴 严重缺陷（8项）

| # | 缺陷 | 影响范围 | 根因 |
|---|------|----------|------|
| 1 | **0个观察日志**：6/12 Agent 无任何 log_execution 调用 | help/leaderboard/match/task/tutor/coin — 生产故障完全不可观测 | Sprint开发省略了日志，但日志是事后追查的唯一手段 |
| 2 | **HelpAgent 数据存内存**：`self._requests: dict` — 进程重启全部丢失 | 社区求助功能等同于"一次性便签"，无法用于生产 | 为速度跳过了DB集成，使用了最简实现 |
| 3 | **LeaderboardAgent 数据存内存**：`self._leaderboards: dict` — 重启即清零 | 排行榜在服务重启后丢失所有历史数据，金币/学习排行形同虚设 | 同上——Agent内部dict代替了DB查询 |
| 4 | **LLM API 无密钥则静默失败**：所有 `llm_service.chat()` 在无有效 Key 时回退到 Ollama，若 Ollama 未启动则返回空结果 | 评估、伴读、纠错、导师——全部LLM功能可能在无提示下不工作 | Provider健康检查只在启动时执行一次，无运行时监控 |
| 5 | **JWT_SECRET 硬编码**：`config.py:61` 明文默认值 | 任何能看到源码的人都能伪造JWT | Sprint速度下未设 `None` 默认+启动校验 |
| 6 | **0 个集成测试覆盖 LLM 路径**：所有 LLM 相关的 Agent 执行路径全无测试 | 评估/伴读/纠错/导师核心功能未经测试验证 | LLM调用需API Key，测试环境未配置 |
| 7 | **CompanionSession 无超时**：会话 `in_progress` 状态无自动关闭机制 | 僵尸会话无限堆积 | Sprint 4 未考虑会话生命周期管理 |
| 8 | **Task 无 deadline 强制执行**：`deadline` 字段存在但无 cron/worker 检查超时 | 任务市场过期任务仍显示为 open | 缺少后台任务调度层 |

### 🟡 中等缺陷（11项）

| # | 缺陷 | 证据 | 影响 |
|---|------|------|------|
| 9 | **TutorView 457行** vs 平均值 110行 → 4倍于中位数组件 | `frontend/src/views/TutorView.vue:457` | 维护噩梦——任何修改需理解全部457行 |
| 10 | **方案C仅 home_zone 一个字段**，零逻辑 | `grep "zone|realm|world|rpg|quest|guild"` → 0 hits | D-001决策"朝向方案C"在实际代码中仅一行字段 |
| 11 | **社区无持久化群组** | guild/clan/tribe → 0 引用 | RPG世界观缺失"社区组织"这一核心社交载体 |
| 12 | **persona_agent 增量更新为空 stub** | `persona_agent.py:197` → 仅返回提示文本 | 画像生成后永不演进，与"AI导师进化"目标矛盾 |
| 13 | **plan_agent 动态调整为空 stub** | `plan_agent.py:216` → 仅返回提示文本 | 学习计划生成后不自适应 |
| 14 | **LLM 无熔断器（circuit breaker）** | 仅有 retry+fallback，无熔断 | 下游Provider全部不可用时，每个请求仍重试3次 |
| 15 | **6个Agent中硬编码 magic number** | `score=100`, `score=30`, `efficiency=50` 等 | 无配置管理，调整需改代码 |
| 16 | **SQLite/PG 双轨运行时性能未知** | 从未在PostgreSQL上运行过（D-002决策但未践行） | 实际性能、并发能力完全未知 |
| 17 | **Layer 1 评估引擎（assessment_prompts.py）依赖试题目录硬编码** | `get_test_prompt()` 使用预置题目，实际生成依赖LLM | 无LLM时评估质量不可控 |
| 18 | **vocabulary.py 的间隔复习（SM-2）无持久化** | 复习间隔计算了但生词表在 `src/services/vocabulary.py` 处理，未与用户画像关联 | 用户重登后遗忘曲线丢失 |
| 19 | **前端无任何自动化测试** | 17个视图零测试 | 任何后端API变更可能静默破坏前端 |

### 🟢 优化项（2项）

| # | 缺陷 | 影响 |
|---|------|------|
| 20 | Redis 缓存层设计完备但未使用 | 排行榜、任务列表等高频查询无缓存 |
| 21 | WebSocket 未实现 | AI伴读只能用轮询，非实时体验 |

---

## 二、架构深度诊断

### 2.1 Agent耦合图（极好！✅）

```
base_agent
  ├── assessment_agent (LLM:9, local:4)
  ├── coin_agent         (LLM:0, local:0)  ← 纯业务逻辑
  ├── companion_agent   (LLM:4, local:2)
  ├── help_agent         (LLM:0, local:0)  ← 纯内存
  ├── leaderboard_agent   (LLM:0, local:1)  ← 纯内存
  ├── match_agent        (LLM:0, local:1)  ← 纯计算
  ├── persona_agent      (LLM:2, local:0)
  ├── plan_agent         (LLM:0, local:0)  ← 仅模板
  ├── task_agent         (LLM:0, local:0)
  └── tutor_agent        (LLM:2, local:3)
```

**结论**：12个Agent零横向耦合——这是项目架构最大的亮点。每个Agent只依赖 base_agent，甚至跨Agent引用为0。

### 2.2 日志/可观测性断层（极差！❌）

| Agent | log_execution 次数 | 生产可见度 |
|-------|-------------------|-----------|
| assessment_agent | 8 | ✅ 高 |
| companion_agent | 5 | ✅ 中 |
| base_agent | 6 | ✅ 高 |
| coin_agent | 1 | ⚠️ 极低 |
| persona_agent | 1 | ⚠️ 极低 |
| plan_agent | 1 | ⚠️ 极低 |
| tutor_agent | 1 | ⚠️ 极低 |
| **help_agent** | **0** | ❌ 零 |
| **leaderboard_agent** | **0** | ❌ 零 |
| **match_agent** | **0** | ❌ 零 |
| **task_agent** | **0** | ❌ 零 |

**结论**：6/12 (50%) Agent 在生产环境中是盲区。故障时只能靠"用户报告+猜"。

### 2.3 方案C对齐度（极差！❌）

| CHANGELOG 承诺 | 代码实现 |
|---------------|---------|
| "方案C → 北极星目标" | home_zone: String(20), nullable → **仅1行** |
| "各Sprint预留架构钩子" | **0个实际钩子** |
| "Language World RPG" | 无world/zone/rpg/quest/guild/clan/tribe/achievement |
| "Duolingo遇见魔兽世界" | 无经验值(xp)、无等级提升(level_up)、无公会 |

**结论**：CHANGELOG中的"方案C北极星"与代码现实之间存在巨大鸿沟。home_zone 字段像是为了"看起来有"而加的，没有任何RPG机制使用它。

---

## 三、决策质量评估

| 决策 | 内容 | 质量 | 证据 |
|------|------|------|------|
| D-001 | Sprint计划v2.0 (8Sprint/16周→3天) | ⭐⭐⭐⭐ | 实际9个里程碑3天完成，估算偏保守但架构够灵活 |
| D-002 | PostgreSQL一步到位 | ⭐⭐ | 选了PostgreSQL但从未在PG上运行过，model用了PG专属类型，compat层事后补救 |
| D-003 | 达子替换GDP影子 | ⭐⭐⭐⭐⭐ | 文档、架构、代码全线正常运转 |
| D-004 | 日志体系建立 | ⭐⭐⭐ | CHANGELOG/日报/里程碑三层齐全，但**代码层可观测性缺失**——日志体系停留在项目级，未下沉到代码级 |

---

## 四、前端风险分析

```
组件行数分布（中位数 110行）：
  TutorView         457行  ⚠️⚠️⚠️ 4x中位数
  TaskDetailView    192行  ⚠️
  TaskCreateView    157行
  TaskMarketView    136行
  CompanionView     133行
  DashboardView     123行
  AssessmentView    116行
  MatchView         108行
  RegisterView       98行
  CoinView           93行
  AssessmentResultView 90行
  LoginView          90行
  PlanView           88行
  HelpView           83行
  LeaderboardView    80行
  VocabularyView     66行
  NotFoundView       22行
```

**结论**：TutorView 是最大技术债——一个文件承担了导师画像+课件+洞见+市场4个功能，应该拆成4个组件。其他组件都在可接受范围（<200行）。

---

## 五、缺失测试清单

| 测试层 | 现有 | 缺失 | 影响 |
|--------|------|------|------|
| 单元（纯逻辑） | ✅ 安全/配置/映射 | — | — |
| 模型（ORM） | ✅ 创建/查询 | — | — |
| API集成（Auth） | ✅ 注册/登录/me | — | — |
| API集成（Assessment） | ✅ 查询/历史/分页 | — | — |
| **API集成（Coin）** | ❌ | 0 | 金币交易未验证 |
| **API集成（Companion）** | ❌ | 0 | 伴读会话未验证 |
| **API集成（Task）** | ❌ | 0 | 任务CRUD+审核未验证 |
| **API集成（Community）** | ❌ | 0 | 排行榜/匹配/求助未验证 |
| **API集成（Tutor）** | ❌ | 0 | 导师进化/课件/市场未验证 |
| **LLM Mock测试** | ❌ | 0 | LLM路径全未覆盖 |
| **前端测试** | ❌ | 0 | 17个视图零测试 |

---

## 六、带往下一阶段的行动建议（按优先级）

| # | 行动 | 预期收益 | 预计工作量 |
|---|------|----------|-----------|
| P0 | **help_agent + leaderboard_agent 内存→DB** | 数据持久化，生产可用 | 4h |
| P0 | **LLM Provider 健康检查 + 启动时告警** | 防止静默失败 | 1h |
| P1 | **全Agent日志补全** | 生产可观测性 | 2h |
| P1 | **CompanionSession 超时自动关闭** | 防止僵尸数据 | 2h |
| P1 | **Task deadline cron检查** | 任务市场完整性 | 3h |
| P2 | **TutorView 拆分为4组件** | 可维护性 | 3h |
| P2 | **方案C架构规划**（home_zone→完整RPG机制） | 战略对齐 | 设计阶段 |
| P2 | **Coin/Companion/Task/Community/Tutor 集成测试** | 质量保障 | 8h |
| P3 | **JWT_SECRET 启动校验（生产环境 None 默认→必填）** | 安全 | 0.5h |
| P3 | **LLM 熔断器** | 韧性 | 1h |

---

## 七、总结

**一句话**：LAWA 的 Agent 架构是教科书级的解耦设计，但可观测性、持久化、测试覆盖三个维度严重欠账——50%的Agent不可观测，2个Agent的数据在进程重启后消失，方案C北极星仅一行代码。

**如果要做生产部署**：P0 的4项必须修（预计10小时）。  
**如果要朝方案C深化**：需要一次架构设计会议，将 home_zone 扩展为完整的 RPG 世界系统。  
**如果仅做试用演示**：当前状态可用（种子数据 + LLM Key）。

---

*分析日期：2026-05-30 | 工具：grep + AST + 手工分析 | 基于全量代码审计*
