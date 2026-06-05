# 🧠 深水复盘：评估系统 Bug 背后的架构法则

**日期**: 2026-06-02 11:20 CST
**作者**: 达子（🦝）
**触发**: Ke 对浅层复盘的质疑 — "还有更深的规则或者法则没有挖掘到位"
**方法**: 从 3 个表面 bug 出发，反向推导 9 层边界中涌现的系统性规律

---

## 零、表面层回顾（快速略过）

三个 bug，逐层剥开：

| 层 | 症状 | 直接原因 | 修复 |
|----|------|----------|------|
| 1 | `result_not_found` | 路由 `:id` vs `sessionId` vs `assessment_id` 三端不对齐 | 统一命名 + localStorage 兜底 |
| 2 | 404 永远返回 | `start_assessment` 只生成 UUID，零 DB 写入 | 加 `_save_question` / `_finalize_assessment` |
| 3 | writing 题超时 | axios 30s < LLM 生成时间 | 提至 60s |

但这不是复盘。这是维修记录。真正的复盘从下面开始。

---

## 一、边界熵增法则（The Boundary Entropy Law）

### 定义

> 在一个由 N 个独立组件构成的系统中，组件间的边界数量为 N-1。每个边界都是一个信息翻译点。如果没有显式契约约束，每个边界上的命名会在时间推移中独立漂移。漂移速率与组件间的组织距离成正比。

### 在本案例中的映射

本系统涉及 **9 个边界**（见下方），在 4 个边界上发生了命名漂移：

```
[localStorage] ──assessment_id──→ [AssessmentView.vue]
                                         │ assessmentId
                                         ▼
                                    [api.post]
                                         │ (payload key: assessment_id)
                                         ▼
                                   [FastAPI Router]
                                         │ req.assessment_id
                                         ▼
                                 [AssessmentAgent]
                                         │ (route param: :id)
                                         ▼
                                   [Vue Router]
                                         │
                                         ▼ (reads: route.params.sessionId)
                              [AssessmentResultView.vue]
                                         │ sessionId
                                         ▼
                                    [api.get]
                                         │ URL: /assessment/result/${sessionId}
                                         ▼
                                   [FastAPI Router]
                                         │ (route: /{assessment_id})
                                         ▼
                                   [Database]
```

**同一个实体**（评估会话 ID）在系统中拥有 **5 个不同的名字**：
- `assessment_id`（payload / agent）
- `assessmentId`（Vue 变量）
- `:id`（路由参数）
- `sessionId`（结果页变量）
- `assessmentId.value`（模板表达式）

### 推论

> **每增加一个组件边界，系统引入命名漂移的概率翻倍。3 个以上独立开发的组件协作时，命名不一致几乎必然发生。**

这不是疏忽。这是熵。只要没有共享类型定义（OpenAPI schema / Protobuf / shared TypeScript types），命名漂移是物理定律般的存在。

### 修复策略（不止于改名）

- **短期**：对齐命名（已完成）
- **中期**：生成 OpenAPI schema，前后端共享类型定义
- **长期**：CI 中加 contract test，检测路由参数名与 API payload key 的一致性

---

## 二、幽灵状态法则（The Phantom State Law）

### 定义

> 当一个系统在内存中维护状态但未持久化时，该状态是"幽灵状态"——它对当前会话可见，但对系统的其他部分（其他 API、后续会话、查询端点）不可见。幽灵状态的典型特征是：开发者感觉系统"工作正常"，因为当前会话中一切正常；但任何超出当前会话的操作都会失败。

### 在本案例中的映射

`start_assessment` 的逻辑：

```python
# 创建了一个"存在"但不是"存在"的东西
assessment_id = str(uuid.uuid4())  # ← 生成了 ID
return {"assessment_id": assessment_id}  # ← 返回了 ID
# 但是：
# - 数据库里没有这条记录
# - GET /assessment/{id} 永远返回 404
# - 除了当前会话的前端内存，世界上没有任何地方知道这个 ID
```

这是一个**幽灵对象**（Phantom Object）：
- ✅ 有 ID
- ✅ 有生命周期（从 start 到 report）
- ❌ 无持久化表示
- ❌ 无查询能力
- ❌ 无审计追踪

### 推论

> **幽灵状态的半衰期 = 单次会话的生命周期。任何依赖幽灵状态的系统，在会话结束后必然失败。幽灵状态的危害不在于它"不工作"，而在于它"看起来工作"——这让 bug 延迟到生产环境才暴露。**

### 为什么这个 bug 特别隐蔽？

因为 `finishAssessment` 做了 `localStorage.setItem('lawa_report_last', ...)`——这是在幽灵状态上打了一个补丁。表面上"报告可以看了"，但实际上：
- 刷新页面 → 报告消失
- 分享链接 → 404
- 查看历史 → 无记录
- 管理员审计 → 无数据

`localStorage` 把幽灵状态延长了一个会话的生命周期，但只是推迟了死亡时间。

### 修复策略

- ✅ 已修复：三个 handler 均写入 DB
- ⚠️ 模式层面：新建 Agent 时必须包含 `_persist()` 生命周期钩子

---

## 三、隐式契约脆弱性法则（The Implicit Contract Fragility Law）

### 定义

> 系统中存在两类契约：显式契约（接口签名、类型定义、Schema）和隐式契约（超时假设、性能假设、可用性假设）。显式契约被打破时立即报错；隐式契约被打破时静默失败，直到下游效应在远处显现。

### 在本案例中的映射

| 隐式契约 | 位置 | 假设内容 | 打破条件 | 下游效应 |
|----------|------|----------|----------|----------|
| 超时契约 | `api/index.ts:4` | "所有 API 调用 30s 内完成" | writing 题 LLM 生成 > 30s | 题目获取失败，维度缺失 |
| 路由契约 | `router/index.ts:8` | "`/assessment/:id` 会被正确传参调用" | `router.push('/assessment/report')` | 参数为 undefined |
| 持久化契约 | `assessment_agent.py:98` | "数据会被某个地方保存" | 无 DB 写入 | GET 端点 404 |
| 数据格式契约 | `AssessmentResultView.vue` | "API 返回格式匹配模板" | report 格式 vs assessment 格式不同 | 字段显示异常 |

### 推论

> **隐式契约的数量与系统复杂度成线性关系。每个未被测试覆盖的隐式契约，在生产环境中是一个定时炸弹。超时值、参数名、响应格式、持久化责任——这些都是隐式契约，它们不会在 IDE 中报错，不会在编译时报错，只会在运行时爆炸。**

---

## 四、倒置测试金字塔法则（The Inverted Testing Pyramid Law）

### 定义

> 经典的测试金字塔主张：大量单元测试 → 适量集成测试 → 少量 E2E 测试。倒置金字塔则相反：零单元测试，零集成测试，唯一的"测试"是开发者在浏览器里手动走通一次 happy path，然后把生产环境当作真正的测试环境。

### 在本案例中的映射

```bash
$ find . -name "*test*" -o -name "*spec*" | grep -v .venv | grep -v node_modules
./frontend/e2e/vue.spec.ts   # ← 内容为 "You did it!" 的默认模板
```

**唯一的测试文件是 Playwright 脚手架生成的默认模板，测试的是一个不存在的 h1 标签。**

9 个边界，零个测试。三个 bug 中的任何一个，只要有一条 E2E 测试覆盖到，就会在部署前暴露：

| Bug | 需要什么测试来捕获 | 测试成本 |
|-----|---------------------|----------|
| 路由不匹配 | 1 条 E2E：启动评估 → 答完 → 验证结果页 URL 合法 | 5 分钟 |
| 零持久化 | 1 条集成测试：POST /start → GET /{id} → 验证 200 | 3 分钟 |
| 超时 | 1 条性能测试：/question?dimension=writing 的 P99 延迟 | 10 分钟 |

**总成本 < 20 分钟。Bug 修复成本：~1 小时。更重要的是发现成本：生产环境暴露。**

### 推论

> **在 N 个组件边界的系统中，至少需要 N 条集成测试覆盖每个边界。缺少的每一条测试，对应一个"等待被发现"的生产 bug。**

---

## 五、组织熵映射法则（Conway's Law in Micro）

### 定义

> 康威定律的微观版本：即使在同一个代码库中，如果两个模块由不同的心智模型（不同时间、不同关注点、不同"完成"标准）构建，它们之间会出现与组织边界相同的熵增效应。

### 在本案例中的映射

四个文件的作者心智模型分析：

| 文件 | 作者心智模型 | "完成"的定义 |
|------|-------------|-------------|
| `assessment_agent.py` | "Agent 负责生成题目和评分" | 返回 dict 即完成 |
| `assessment.py` (routes) | "路由负责转发请求" | 参数校验通过即完成 |
| `AssessmentView.vue` | "页面负责展示题目和收集答案" | 答完题即完成 |
| `AssessmentResultView.vue` | "页面负责展示报告" | 显示数据即完成 |

**四个作者（即使是同一个人在不同时间写的），四个不同的"完成"定义。没有一个人的"完成"包含"确保评估全流程端到端可用"。**

### 推论

> **即使是一个人的代码库，如果开发是按"组件"而非"流程"组织的，就会出现康威熵。跨越 3 个以上组件的用户流程，必须有明确的流程所有者——在 LAWA 中，这个角色是缺失的。**

---

## 六、终极法则：集成表面积爆炸（The Integration Surface Area Explosion）

### 定义

> 一个横切 N 个组件的用户流程，其故障概率 = 1 − (1−p)^k，其中 k 是集成点数量，p 是每个集成点的故障概率。K 值不是 N（组件数），而是 N(N−1)/2（组件间的交互对数）。

### 在本案例中的映射

评估流程的完整集成图：

```
组件: A(localStorage) B(AssessmentView) C(api/axios) D(Router) 
      E(API route) F(Agent) G(LLM svc) H(ResultView) I(DB)

边界（集成点）= 9
潜在交互对数 = 9×8/2 = 36

实际出问题的边界：3
- B→D (路由跳转)
- H→E (API 调用)
- E→F→I (持久化链)
```

### 推论

> **当流程跨越 9 个组件时，即使每个组件 95% 可靠，端到端可靠性 = 0.95^9 ≈ 63%。三个 bug 不是意外，是统计学上的必然。**

---

## 七、总结：修复了什么 vs 学到了什么

### 修复了

- [x] 3 个表面 bug
- [x] 4 个文件的代码改动
- [x] DB 持久化路径

### 学到了（这部分的 ROI 远超代码修复）

| # | 法则 | 一句话 |
|---|------|--------|
| 1 | 边界熵增 | 没有共享类型 = 命名必然漂移 |
| 2 | 幽灵状态 | 内存数据不是数据，持久化才是 |
| 3 | 隐式契约 | 编译不报错 ≠ 运行不错 |
| 4 | 倒置测试 | 唯一的 E2E 测试是默认脚手架模板 |
| 5 | 微观康威 | 按组件开发 = 流程所有权真空 |
| 6 | 集成表面 | 9 组件 × 95% 可靠 = 63% 端到端可靠 |

### 行动项（按优先级）

1. **P0**：为评估全流程写 1 条 E2E 测试（start → answer × N → result page renders）
2. **P1**：从路由/API 层生成 OpenAPI schema，前后端共享类型
3. **P1**：Agent 基类增加 `_persist()` 生命周期钩子
4. **P2**：API 端点按特性分级超时（快 < 10s / 中 < 30s / LLM < 90s）
5. **P2**：CI 加 contract test：路由参数名 ↔ API payload key 一致性检查

---

*"Bug 是系统在对你说话。浅层听是报错信息，深层听是架构法则。"*
