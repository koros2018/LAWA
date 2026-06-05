# LAWA 项目复盘报告

> 复盘人：达子 🦝 | 日期：2026-05-30  
> 范围：M0~M9 全里程碑（2026-05-27 ~ 05-30，3天）  
> 方法：数据驱动 + 根因分析 + 行动项

---

## 一、全貌数据

| 维度 | 数值 |
|------|------|
| 开发周期 | 3天（05/27 → 05/30） |
| 里程碑 | 9个（M0~M9），全部完成 |
| Sprint 节奏 | Day1: 4连击 / Day2: 3个 / Day3: 2个 |
| 代码总量 | ~10,800行（Python 7400 + Vue 2700 + 测试 700） |
| 文件数 | 57+ (src 37 + frontend 20 + tests 7 + infra 6) |
| API 端点 | 56个（Auth/Assessment/Coin/Companion/Task/Community/Tutor） |
| 测试覆盖 | 68个测试（0→68，收官日集中补充） |
| 数据表 | 7张（users / profiles / assessments / tasks / coins / companion / tutor） |
| Agent 数 | 12个 |
| LLM Provider | 3个（NVIDIA NIM / OpenCode / Ollama 兜底） |

---

## 二、时间线还原

```
05/27 下午  Ke发起项目 → 达子接替"GDP影子" → 确立方案C北极星
           ├─ D-001~004 决策（PostgreSQL / 达子署名 / 日志体系）
           └─ Sprint 0→1→2→3 一天四连击（~4500行，40/41任务）

05/28      Sprint 4: AI伴读（~1800行，7文件）
           ├─ 纠错引擎 + 生词提取 + SM-2间隔复习
           └─ Sprint 5: 前端MVP（~1340行，17视图）
           Sprint 6: 任务市场（~1350行）

05/29      Sprint 7: 社区引擎（~860行，3文件）
           └─ Sprint 8: AI导师进化（~1242行，3文件）
           M0~M8 全部里程碑完成 🎉

05/30      收官日：M9 质量保证 & 试用准备
           ├─ 测试：0→68个全绿
           ├─ Bug修复：9个（🔴3个严重 + 🟡5个中等 + 🟢1个优化）
           ├─ 数据: alembic迁移 + 种子数据 + 启动脚本
           └─ 文档: README更新 + DEMO.md试用指南
```

---

## 三、做得好的（Keep Doing）

### 3.1 Agent 架构模式 ✅
每个业务域一个Agent，`execute(payload) → result` 统一接口。  
**证据**：12个Agent开发顺畅，无架构重构。路由层极薄（仅参数校验→调用Agent→返回）。

### 3.2 LLM 多Provider抽象 ✅
`llm_service` 统一管理3个Provider（NVIDIA/OpenCode/Ollama），Agent层无需关心路由。  
**证据**：Day1配置NVIDIA后，Day2/3新增OpenCode/Ollama零改动Agent代码。

### 3.3 Sprint 节奏（批量突击） ✅
Day1四连击极其高效——因为脚手架、评估、画像、金币有四层依赖，顺次开发无阻塞。  
**证据**：4500行/天，代码质量后续审计仅发现字段名不一致等小问题。

### 3.4 文档体系 ✅
CHANGELOG（决策追溯）+ 日报（进展可查）+ MILESTONES（进度一目了然）。  
**证据**：本次复盘所有数据均可从记忆文件中还原。

---

## 四、做得差的（根因分析）

### 🔴 问题1：认证端点全空壳（501）跨越8个Sprint未发现

**表象**：register/login/me 三个端点返回 `501 Not Implemented`，直到收官日测试才发现。

**根因链**：
```
前端优先于后端验证 → 前端用 mock 数据开发，没连真实后端
→ 其他路由也未做集成测试 → 没人触发过 /api/v1/auth/register
→ 代码审查缺失 → TODO注释在 diff 中不可见
→ 单开发者无交叉检查
```

**教训**：即便前端mock，核心端点（auth）应该在M0完成后立即端到端验证。

### 🔴 问题2：SQLite测试失败（PostgreSQL类型不兼容）

**表象**：D-002决策用PostgreSQL，但测试用SQLite，6个模型文件直接引用 `sqlalchemy.dialects.postgresql`。

**根因链**：
```
compat.py 兼容层已存在 → 但模型文件没有用它
→ 因为开发时没跑SQLite（PostgreSQL未启动但也没测）
→ 测试是最后补的 → 发现时已有大量代码
```

**教训**：兼容层和模型应该在同一个Sprint内对齐。决策"PostgreSQL一步到位"应与"测试用SQLite"配合一个兼容策略。

### 🟡 问题3：0测试到68测试全部收官日补充

**根因**：Sprint模式注重功能交付速度，测试被明确推迟（"完整测试留给Sprint后用"）。

**影响**：
- 认证空壳跨越9个里程碑未被发现
- 模型字段不兼容到收官日才暴露
- passlib/bcrypt版本冲突到测试时才暴露

**这个决策本身不算错**（速度优先），但代价在收官日集中爆发——修复9个bug + 写68个测试，收尾工作量远超预期。

### 🟡 问题4：Docker验证被跳过

**根因**：WSL2环境 Docker Desktop 未启动，但 docker-compose.yml 和 Dockerfile 已写好。

**风险**：虽然文件齐全，但未经实际构建验证，部署时可能有未知问题。

### 🟡 问题5：配置文件安全隐患

- `JWT_SECRET` 默认值 `lawa-dev-secret-change-in-production`（明文在 config.py 默认值中）
- `.env.example` 中 `DB_PASSWORD=***`（实际弱密码）
- 生产环境无强密码策略

---

## 五、技术债清单

| 级别 | 项目 | 文件 | 影响 |
|------|------|------|------|
| 🟡 | persona_agent 增量更新 stub | `persona_agent.py:197` | 画像不随时间演进 |
| 🟡 | plan_agent 动态调整 stub | `plan_agent.py:216` | 学习计划不会自适应 |
| 🟡 | base_agent 旧 TODO 残留 | `base_agent.py:52` | 已修复为委托 llm_service |
| 🟡 | 前端无自动化测试 | `frontend/src/` | 17视图纯手工验证 |
| 🟢 | Redis 缓存未使用 | — | 可加但非阻塞 |
| 🟢 | WebSocket 未实现 | — | 计划中的功能 |

---

## 六、如果重来一次（反事实推演）

### 6.1 我会改变的3件事

1. **M0 完成立即写 auth 集成测试**  
   哪怕只是一个 `test_register_login_flow`，也能在 Day1 发现 501 空壳。

2. **模型文件强制用 compat 层，加 pre-commit 检查**  
   `grep "from sqlalchemy.dialects.postgresql"` 一行脚本在每次 commit 前跑。

3. **每个 Sprint 收尾 5 分钟跑一次 `pytest`（哪怕0个测试也跑语法检查）**  
   成本极低，收益巨大。

### 6.2 不改的3件事

1. **Agent 架构** — 12个Agent零架构冲突，别动。
2. **Sprint 批处理节奏** — 依赖链上的一天四连击是对的，别拆。
3. **文档体系** — CHANGELOG+日报+里程碑三层够了，别加。

---

## 七、带往下一个项目的行动项

| # | 行动 | 优先级 |
|---|------|--------|
| 1 | **Day 0 建测试骨架**：conftest + 1个集成测试（哪怕只测 health） | 🔴 |
| 2 | **核心端点 Day 1 跑通**：auth register→login→me 链路验证 | 🔴 |
| 3 | **数据库兼容从模型建完就开始**：强制用 compat 层，加上检查脚本 | 🔴 |
| 4 | **每日收尾跑全量测试**：`pytest` 作为 commit 前必做步骤 | 🟡 |
| 5 | **Docker 验证不拖到收官**：Sprint 2 开始每个 sprint 跑一次 `docker compose build` | 🟡 |
| 6 | **敏感配置不设默认值**：JWT_SECRET 等用 `None` 默认 + 启动时校验必填 | 🟡 |

---

## 八、总体评价

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构设计 | ⭐⭐⭐⭐⭐ | Agent模式+多Provider+compat层，经受住了3天高速迭代 |
| 功能完整度 | ⭐⭐⭐⭐☆ | 56端点全部可调用，LLM依赖除外 |
| 代码质量 | ⭐⭐⭐⭐☆ | 语法100%通过，9个bug在收官日集中修复 |
| 测试覆盖 | ⭐⭐⭐☆ | 68个测试但都是收官日补的，缺失前端测试和LLM集成测试 |
| 文档 | ⭐⭐⭐⭐⭐ | README/CHANGELOG/日报/DEMO四层齐全 |
| 可部署性 | ⭐⭐⭐☆ | Docker文件齐全但未实际验证，依赖LLM API |

**一句话总结**：3天从0到56端点，架构扛住了极速迭代，但"先冲后补测试"的策略让收官日变成排雷日。下个项目第一天就种测试。

---

*复盘日期：2026-05-30 16:04 CST | 复盘人：达子 🦝*
