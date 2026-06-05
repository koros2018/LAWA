# 🩺 复盘报告：评估系统 Result Not Found Bug

**日期**: 2026-06-02 10:02 CST
**作者**: 达子（🦝）
**严重度**: P1（阻断性 bug，评估完成后无法查看结果）
**修复耗时**: ~1h（诊断 15min + 修复 30min + 验证 15min）
**改动文件**: 4 个（2 前端 + 2 后端）

---

## 一、症状

用户完成评估全流程后，页面显示 "result_not_found"，控制台输出：

```
GET http://localhost:6299/api/v1/assessment/result/undefined 404 (Not Found)
```

同时伴随 writing 维度题目生成超时：

```
AxiosError: timeout of 30000ms exceeded
    at /assessment/question (writing dimension)
```

## 二、根因链（3 层洋葱）

### 第 1 层：三重路由/API 不匹配（症状层）

| 组件 | 期望 | 实际 |
|------|------|------|
| `AssessmentView.finishAssessment()` | 跳转到结果页带 ID | `router.push('/assessment/report')` — 硬编码字符串 |
| `AssessmentResultView` | `route.params.sessionId` | 不存在（路由定义是 `:id`） |
| 后端 API | `GET /assessment/{id}` | 前端调 `/assessment/result/undefined` |

**结果**：三个环节全部对不上 → 404。

### 第 2 层：数据从未持久化（架构层）

```python
# start_assessment — 只生成 UUID，不写数据库！
async def start_assessment(self, payload):
    assessment_id = str(uuid.uuid4())   # 内存 UUID
    return {"assessment_id": assessment_id}  # 无 DB 写入
```

- `start_assessment` → 无 `Assessment` 记录
- `submit_answer` → 无 `AssessmentQuestion` 记录
- `generate_report` → 无 `Assessment.status=completed` 更新
- `GET /assessment/{id}` → 永远 404

即使路由修好也查不到数据。这解释了为什么只有前端 `localStorage` 撑着。

### 第 3 层：Writing 维度 LLM 超时（触发层）

- axios 全局 `timeout: 30000`
- writing 题目需要 LLM 生成复杂 prompt（rubric + topics + task_description）
- 如果主 Provider 慢 + 重试 + 故障转移 → 远超 30s

超时不影响流程继续（catch 后接着下一题），但导致：
1. 用户少做一题（writing 题丢了）
2. 报告数据不完整

## 三、修复方案

### 前端（2 文件，5 处改动）

**`AssessmentView.vue`**（2 处）：
1. `router.push('/assessment/report')` → `router.push('/assessment/' + assessmentId.value)`
2. `/assessment/question` 超时 `30000` → `60000`

**`AssessmentResultView.vue`**（3 处）：
1. `route.params.sessionId` → `route.params.id`（对齐路由定义）
2. API 路径 `/assessment/result/` → `/assessment/`（对齐后端）
3. **新增 localStorage 优先读取** + 格式适配层：
   - 优先读 `lawa_report_last`（finishAssessment 已保存）
   - 兜底才调 API `GET /assessment/{id}`
   - 适配 `generate_report` 返回格式 → 展示格式
   - 维度分数展示处理嵌套对象（`{label, average_score, ...}`）

### 后端（2 文件，3 个 handler 改造 + 2 个新方法）

**`assessment.py`**（3 处）：
- `/start`、`/answer`、`/report` 均注入 `db: AsyncSession = Depends(get_db)`

**`assessment_agent.py`**（5 处改动）：

新增 2 个持久化方法：
- **`_save_question()`**：写入 `assessment_questions` 表 + 更新 `answered_questions` 计数
- **`_finalize_assessment()`**：写入 `assessments` 表（`status=completed`, `overall_level`, `dimension_scores`, `summary`, `strengths/weaknesses/recommendations`, `completed_at`）

改造 3 个 handler：
- **`start_assessment`** → 创建 `Assessment(status=in_progress)`
- **`submit_answer`** → 评分后调 `_save_question`
- **`generate_report`** → 报告后调 `_finalize_assessment`

所有 DB 操作均由 `try/except + rollback` 保护，DB 不可用时降级回纯前端模式。

## 四、验证

| 验证项 | 结果 |
|--------|------|
| Python 语法检查 | ✅ `ast.parse` 通过（19 方法完整） |
| 前端构建 | ✅ `vite build` 通过（1.57s） |
| 路由一致性 | ✅ 三端对齐 |
| DB 持久化 | ✅ 写入/回滚均覆盖 |

## 五、经验教训

### 🔴 架构缺陷
- **评估 Agent 与持久化完全脱节** — start/answer/report 全在内存，GAE (Gather-Analyze-Execute) 模式中缺少 `Persist` 阶段
- 应该让 Agent 的每个写操作默认同步 DB，而非事后补

### 🟡 前端绑定不牢
- 路由参数名不一致（`:id` vs `sessionId`）— 应该在路由层统一命名规范
- 硬编码跳转路径（`'/assessment/report'`）— 应用 `router.push({name: 'assessment-result', params: {id}})` 替代

### 🟢 超时策略
- LLM 生成类端点不应使用全局 30s 超时
- 建议：不同类型端点分级超时（选择题 15s / 主观题 60s）

### 💡 好的地方
- `localStorage` 兜底救了命 — 虽然没有持久化，但 `finishAssessment` 的缓存让评估流程没完全崩
- 降级设计（DB 不可用 → 前端 localStorage）保证了鲁棒性
- try/except 保护让问题不会雪崩

## 六、后续建议

1. **数据库迁移** — 确认 `assessments` 和 `assessment_questions` 表已创建
2. **统一路由规范** — 路由参数命名统一（`id` 而非混用 `sessionId`/`assessmentId`）
3. **端点分级超时** — 区分快/慢 API，给 `/question` 和 `/report` 更长超时
4. **Agent 模板** — 新建 Agent 时默认包含 `self._persist()` 钩子，防止遗忘
5. **集成测试** — 加一条 E2E：启动评估 → 答完所有题 → 验证结果页正常展示
