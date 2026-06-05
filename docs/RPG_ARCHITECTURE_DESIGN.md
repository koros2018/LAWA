# LAWA RPG 世界系统架构设计文档

> **会议主题**: 方案C深化 — 将 `home_zone` 扩展为完整的 RPG 世界系统
> **日期**: 2026-05-31
> **状态**: 🟡 架构设计阶段（等待 Ke 确认）
> **基于**: DEFECTS_AND_DEBT.md #10, RETROSPECTIVE.md 第6点

---

## 📋 会议纪要与行动项

### 现状诊断
| 问题 | 证据 |
|------|------|
| `home_zone` 仅一个字段 | `Mapped[String(20), nullable=True]`，零逻辑使用 |
| RPG 核心概念完全缺失 | grep "world\|zone\|rpg\|quest\|guild\|tribe\|achievement" → 0 hits |
| 架构图无 RPG 层 | ARCH.md 中无 world/zone/rpg 任何模块 |
| SPRINT 预留未兑现 | S8-06 "World Map API" 仅为骨架 |

### 核心目标
实现 **"Duolingo 遇见 魔兽世界"** 的语言学习 RPG 化：
- 语言水平 → 角色等级 / 职业
- 学习任务 → RPG 副本 / 任务链
- 金币经济 → 游戏内经济 + 装备系统
- 社区互助 → 公会 / 联盟系统
- AI 导师 → NPC 导师 / 智能向导

---

## 🏗 六大子系统架构蓝图

### 1. 世界地图与区域系统（World / Zone）

**替代**: 现有 `home_zone` 字段

**新增数据模型**:
```sql
-- 语言区域（大洲级别）
language_zones (
    id UUID PRIMARY KEY,
    code VARCHAR(10) UNIQUE,           -- "en-uk", "zh-cn"
    name VARCHAR(100),                   -- "英美联邦"
    culture_theme VARCHAR(50),           -- "维多利亚蒸汽朋克"
    native_lang VARCHAR(5),              -- "en"
    unlock_requirement VARCHAR(20),      -- "CEFR B1" / "HSK3"
    map_position JSON,                   -- {"x": 120, "y": 80}
    connected_zones UUID[],            -- 相邻区域
    created_at TIMESTAMP
);

-- 区域内具体场景（城市/建筑/地点）
zone_nodes (
    id UUID PRIMARY KEY,
    zone_id UUID REFERENCES language_zones,
    code VARCHAR(20) UNIQUE,             -- "london-grammar-guild"
    name VARCHAR(100),                   -- "伦敦语法公会"
    node_type VARCHAR(20),               -- "city" | "dungeon" | "market" | "academy"
    skill_focus VARCHAR(20),           -- "grammar" | "reading" | "writing" | "speaking"
    cefr_min VARCHAR(5),                 -- 最低进入等级
    cefr_max VARCHAR(5),                 -- 推荐最高等级
    daily_quest_pool UUID[],             -- 可生成的日常任务模板
    npc_dialogue JSON,                   -- 区域NPC对话脚本
    created_at TIMESTAMP
);

-- 区域间通道
zone_connections (
    id UUID PRIMARY KEY,
    from_zone_id UUID REFERENCES language_zones,
    to_zone_id UUID REFERENCES language_zones,
    travel_cost INT DEFAULT 0,           -- 金币消耗
    travel_time INT DEFAULT 0,           -- 虚拟时间（秒）
    unlock_condition VARCHAR(100),       -- "完成B1评估" / "拥有航海图道具"
    created_at TIMESTAMP
);
```

**核心机制**:
- **出生点**: 根据 `native_lang` 自动分配初始区域（zh-cn → 华夏区，en → 英美区）
- **区域解锁**: 通过语言里程碑解锁新区域（如达成 B2 解锁英美区高级副本）
- **跨区域旅行**: 消耗金币/时间，获得文化奖励（首次进入新区域奖励 XP）

**API 端点**:
```
GET  /api/v1/world/zones              # 世界地图（全部区域）
GET  /api/v1/world/zones/{zone_id}    # 区域详情
GET  /api/v1/world/zones/{zone_id}/nodes  # 区域内场景
POST /api/v1/world/travel             # 跨区域旅行
GET  /api/v1/world/user-position      # 用户当前位置
```

---

### 2. 角色成长系统（Character Progression）

**替代**: 现有简单等级/经验

**扩展 `lawa_profiles` 表**:
```sql
ALTER TABLE lawa_profiles ADD COLUMN:
    character_class VARCHAR(20),         -- "translator" | "teacher" | "writer" | "traveler" | "diplomat"
    xp INT DEFAULT 0,                    -- 经验值
    level INT DEFAULT 1,                 -- 角色等级（与语言水平解耦）
    talent_points INT DEFAULT 0,         -- 天赋点（升级获得）
    skill_tree JSON DEFAULT '{}',        -- {"grammar": 3, "reading": 5, "writing": 2, ...}
    title VARCHAR(50),                   -- 称号（如"语法猎人"）
    avatar_config JSON                   -- 角色外观配置
```

**语言职业设计**:
| 职业 | 专精 | 金币加成 | 适合学习者 |
|------|------|---------|-----------|
| **创业者** | 翻译/转换/资源整合 | 互助任务 +20% | 双语能力强的用户 |
| **金融从业者** | 教学/纠错/分析 | 帮助收益 +25% | 乐于助人型 |
| **工程师** | 写作/创作/构建 | 写作任务 +30% | 技术内容创作者 |
| **互联网观察员** | 口语/文化/趋势 | 文化探索 XP +40% | 实用主义型 |
| **国际观察员** | 综合/谈判/视野 | 全任务 +10% | 高阶学习者 |

**经验值来源**:
```
学习10分钟        → +5 XP
完成日常任务      → +20 XP
帮助他人纠错      → +15 XP（按质量浮动）
通过副本          → +50~200 XP（按难度）
首次解锁区域      → +100 XP
连续登录7天       → +50 XP
公会贡献          → +10 XP / 次
```

**等级公式**: `level = floor(√(xp / 100)) + 1`
- Lv1: 0 XP | Lv5: 1,600 XP | Lv10: 8,100 XP | Lv20: 36,100 XP

**天赋树**（每次升级获得 1 点）:
```
听说读写四大分支，每分支 5 级：
  ├─ 听力分支: 听速+10% / 口音识别 / 连读捕捉
  ├─ 口语分支: 流利度+10% / 发音精准 / 即兴表达
  ├─ 阅读分支: 阅读速度+10% / 长难句解析 / 速读
  └─ 写作分支: 语法纠错+10% / 修辞鉴赏 / 创意写作
```

**Agent 规划**: `CharacterAgent` — 经验计算、等级提升、天赋分配

---

### 3. 任务与副本系统（Quest / Dungeon）

**增强**: 现有任务市场（Sprint 6 Task）

**数据模型**:
```sql
-- 任务模板库
quest_templates (
    id UUID PRIMARY KEY,
    code VARCHAR(30) UNIQUE,
    name VARCHAR(100),
    description TEXT,
    quest_type VARCHAR(20),            -- "daily" | "weekly" | "main" | "side" | "dungeon" | "raid"
    difficulty INT,                    -- 1~10
    skill_focus VARCHAR(20),           -- "grammar" | "vocabulary" | "reading" | ...
    cefr_target VARCHAR(5),            -- 推荐水平
    xp_reward INT,
    coin_reward INT,
    item_reward UUID[],                -- 可能掉落的装备/道具
    pre_quest_id UUID,                 -- 前置任务
    time_limit INT,                    -- 限时（秒），NULL=不限时
    content JSON,                      -- 任务具体内容（LLM生成或预置）
    created_at TIMESTAMP
);

-- 用户任务实例
user_quests (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    quest_template_id UUID REFERENCES quest_templates,
    status VARCHAR(20),                -- "accepted" | "in_progress" | "completed" | "failed" | "expired"
    progress JSON DEFAULT '{}',        -- {"answered": 3, "correct": 2}
    accepted_at TIMESTAMP,
    completed_at TIMESTAMP,
    expires_at TIMESTAMP               -- 日常/周常过期时间
);

-- 副本实例（多人/限时挑战）
dungeon_instances (
    id UUID PRIMARY KEY,
    dungeon_template_id UUID,
    host_user_id UUID REFERENCES users,
    participant_ids UUID[],            -- 参与者
    status VARCHAR(20),                -- "waiting" | "active" | "completed" | "failed"
    current_phase INT DEFAULT 1,       -- 副本阶段
    team_score INT DEFAULT 0,
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);
```

**副本类型设计**:
| 副本 | 类型 | 人数 | 时长 | 内容 |
|------|------|------|------|------|
| **机场通关** | daily | 1 | 10min | 模拟值机/安检/登机对话 |
| **商务谈判** | dungeon | 1~3 | 20min | 角色扮演商务会议 |
| **学术讨论** | dungeon | 1~2 | 15min | 论文摘要辩论 |
| **多语言剧场** | raid | 3~5 | 30min | 团队协作演绎剧本 |

**API 端点**:
```
GET  /api/v1/quests/daily              # 今日日常任务（3个）
GET  /api/v1/quests/weekly             # 本周周常
GET  /api/v1/quests/main-line          # 主线任务链
POST /api/v1/quests/{quest_id}/accept  # 接取任务
POST /api/v1/quests/{quest_id}/submit  # 提交完成
GET  /api/v1/dungeons/available        # 可进入副本列表
POST /api/v1/dungeons/{id}/join        # 加入副本队伍
POST /api/v1/dungeons/{id}/start     # 房主启动副本
```

**Agent 规划**: `QuestAgent` — 任务生成、进度追踪、副本管理

---

### 4. 公会与社交系统（Guild / Clan / Tribe）

**替代**: 现有基本匹配（MatchAgent）

**数据模型**:
```sql
-- 语言公会
language_guilds (
    id UUID PRIMARY KEY,
    name VARCHAR(100),
    tag VARCHAR(10) UNIQUE,            -- 公会标签，如 "[ENGL]"
    description TEXT,
    lang_focus VARCHAR(5),             -- 主要语言
    level_requirement VARCHAR(5),      -- 入会最低等级
    max_members INT DEFAULT 50,
    current_members INT DEFAULT 1,
    guild_xp INT DEFAULT 0,            -- 公会经验
    guild_level INT DEFAULT 1,         -- 公会等级
    treasury_coins INT DEFAULT 0,      -- 公会资金
    buff_active JSON DEFAULT '{}',     -- 当前激活的BUFF
    created_by UUID REFERENCES users,
    created_at TIMESTAMP
);

-- 公会成员
 guild_members (
    id UUID PRIMARY KEY,
    guild_id UUID REFERENCES language_guilds,
    user_id UUID REFERENCES users,
    role VARCHAR(20),                  -- "leader" | "officer" | "member" | "newbie"
    joined_at TIMESTAMP,
    guild_contribution INT DEFAULT 0,  -- 贡献值
    last_active TIMESTAMP
);

-- 公会任务（公会专属）
guild_quests (
    id UUID PRIMARY KEY,
    guild_id UUID REFERENCES language_guilds,
    quest_template_id UUID REFERENCES quest_templates,
    status VARCHAR(20),
    collective_progress INT DEFAULT 0, -- 集体进度
    target_progress INT,               -- 目标
    reward JSON,                       -- 公会奖励
    expires_at TIMESTAMP
);

-- 公会竞技记录
interguild_wars (
    id UUID PRIMARY KEY,
    challenger_guild_id UUID REFERENCES language_guilds,
    defender_guild_id UUID REFERENCES language_guilds,
    war_type VARCHAR(20),              -- "quiz" | "translation" | "speed"
    status VARCHAR(20),                -- "pending" | "active" | "ended"
    winner_guild_id UUID REFERENCES language_guilds,
    score JSON,                        -- {"challenger": 850, "defender": 720}
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);
```

**公会 BUFF 设计**:
| BUFF | 效果 | 解锁条件 |
|------|------|---------|
| 全员金币+10% | 金币获取加成 | 公会 Lv3 |
| 每日任务+1 | 额外日常任务 | 公会 Lv5 |
| 副本XP+15% | 副本经验加成 | 公会 Lv7 |
| 学习加速 | 学习时长换算+20% | 公会 Lv10 |

**API 端点**:
```
POST /api/v1/guilds                    # 创建公会
GET  /api/v1/guilds                  # 公会列表
POST /api/v1/guilds/{id}/join        # 申请加入
POST /api/v1/guilds/{id}/leave       # 退出公会
GET  /api/v1/guilds/{id}/quests      # 公会任务
POST /api/v1/guilds/{id}/wars/challenge  # 发起公会战
```

**Agent 规划**: `GuildAgent` — 公会管理、公会战、公会任务

---

### 5. 装备与道具系统（Equipment / Items）

**增强**: 现有金币经济（CoinAgent）

**数据模型**:
```sql
-- 物品定义
item_definitions (
    id UUID PRIMARY KEY,
    code VARCHAR(30) UNIQUE,
    name VARCHAR(100),
    description TEXT,
    item_type VARCHAR(20),             -- "equipment" | "consumable" | "material" | "collectible"
    rarity VARCHAR(10),                -- "common" | "rare" | "epic" | "legendary"
    equip_slot VARCHAR(20),            -- "head" | "body" | "weapon" | "accessory" | NULL
    stat_bonuses JSON,                 -- {"reading_speed_pct": 20, "accuracy_pct": 15}
    effect_duration INT,               -- 效果持续秒数（消耗品）
    sell_price INT DEFAULT 0,
    created_at TIMESTAMP
);

-- 用户物品栏
user_inventory (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    item_id UUID REFERENCES item_definitions,
    quantity INT DEFAULT 1,
    equipped BOOLEAN DEFAULT FALSE,
    durability INT DEFAULT 100,        -- 耐久度
    acquired_at TIMESTAMP
);

-- 合成配方
crafting_recipes (
    id UUID PRIMARY KEY,
    result_item_id UUID REFERENCES item_definitions,
    ingredients JSON,                    -- [{"item_id": "...", "qty": 3}]
    coin_cost INT DEFAULT 0,
    required_level INT DEFAULT 1
);
```

**装备示例**:
| 装备 | 部位 | 效果 | 稀有度 |
|------|------|------|--------|
| **魔法词典** | weapon | 词汇记忆速度+25% | rare |
| **时光沙漏** | accessory | 学习时长换算+30% | epic |
| **翻译之眼** | head | 长难句解析准确率+20% | rare |
| **文化罗盘** | body | 文化探索XP+15% | common |
| **免死金牌** | consumable | 副本失败不扣XP | epic |
| **双倍卡** | consumable | 下一次学习XP×2 | rare |

**合成系统**:
```
3× 生词碎片 + 50金币 → 1× 魔法词典
2× 语法笔记 + 1× 修辞精华 → 1× 翻译之眼
```

**API 端点**:
```
GET  /api/v1/inventory                 # 我的物品栏
POST /api/v1/inventory/{item_id}/equip  # 装备物品
POST /api/v1/craft                     # 合成物品
GET  /api/v1/shop                      # 公会商店/世界商店
POST /api/v1/shop/buy                  # 购买物品
```

**Agent 规划**: `InventoryAgent` — 物品管理、合成、商店

---

### 6. 成就与收藏系统（Achievements / Collections）

**新增系统**（LAWA 现有无成就体系）

**数据模型**:
```sql
-- 成就定义
achievements (
    id UUID PRIMARY KEY,
    code VARCHAR(30) UNIQUE,
    name VARCHAR(100),
    description TEXT,
    category VARCHAR(20),              -- "milestone" | "challenge" | "collection" | "social"
    icon_url VARCHAR(255),
    condition_type VARCHAR(20),      -- "level_reached" | "quest_completed" | "streak" | "collection"
    condition_value JSON,              -- {"level": 10} / {"quest_count": 100}
    reward_xp INT DEFAULT 0,
    reward_coins INT DEFAULT 0,
    reward_item_id UUID REFERENCES item_definitions
);

-- 用户成就
user_achievements (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users,
    achievement_id UUID REFERENCES achievements,
    unlocked_at TIMESTAMP
);

-- 收藏套装
collection_sets (
    id UUID PRIMARY KEY,
    code VARCHAR(30) UNIQUE,
    name VARCHAR(100),
    description TEXT,
    items_required UUID[],               -- 需要集齐的物品ID
    reward_effect JSON                   -- 集齐奖励
);

-- 里程碑故事（剧情解锁）
milestone_stories (
    id UUID PRIMARY KEY,
    trigger_condition VARCHAR(100),      -- "level:10" / "zone:first_enter:en-uk"
    title VARCHAR(200),
    content TEXT,                        -- LLM生成的剧情文本
    dialogue JSON,                       -- NPC对话
    reward JSON
);
```

**成就示例**:
| 成就 | 条件 | 奖励 |
|------|------|------|
| **初出茅庐** | 达到 Lv5 | +100 XP |
| **语法猎人** | 完成 50 个语法任务 | +200 XP + 魔法词典 |
| **周常达人** | 连续 7 天完成日常 | +500 XP + 称号 |
| **百次纠错** | 帮助他人纠错 100 次 | +300 XP + 讲师专属装备 |
| **世界公民** | 解锁 2 个语言区域 | +1000 XP + 文化罗盘 |
| **收藏大师** | 集齐"世界问候大全"套装 | 全属性+5% BUFF |

**API 端点**:
```
GET  /api/v1/achievements              # 成就列表
GET  /api/v1/achievements/mine         # 我的成就
GET  /api/v1/collections               # 收藏套装
GET  /api/v1/stories                   # 已解锁剧情
GET  /api/v1/stories/{story_id}        # 剧情详情
```

**Agent 规划**: `AchievementAgent` — 成就检测、收藏追踪、剧情解锁

---

### 7. 在线总架构师系统（Meta Architect）

**新增系统** — LAWA 的"元级大脑"

**职责**: 负责监督、优化、进化整个 LAWA 系统

**数据模型**:
```sql
-- 系统健康监控快照
system_health_snapshots (
    id UUID PRIMARY KEY,
    agent_name VARCHAR(50),              -- 被监控的Agent
    status VARCHAR(20),                  -- "healthy" | "degraded" | "critical"
    metrics JSON,                        -- {latency_ms, error_rate, memory_mb, ...}
    issues JSON,                         -- [{"type": "no_log", "severity": "medium"}]
    recommendation TEXT,                 -- AI生成的优化建议
    snapshot_at TIMESTAMP
);

-- 架构改进提案
architecture_proposals (
    id UUID PRIMARY KEY,
    title VARCHAR(200),
    description TEXT,
    category VARCHAR(30),                -- "performance" | "reliability" | "evolution" | "security"
    priority VARCHAR(10),                -- "P0" | "P1" | "P2" | "P3"
    status VARCHAR(20),                  -- "draft" | "review" | "approved" | "implemented"
    affected_components JSON,            -- ["help_agent", "coin_agent"]
    diff_summary TEXT,                   -- 变更摘要
    auto_apply BOOLEAN DEFAULT FALSE,    -- 是否自动实施
    created_at TIMESTAMP,
    implemented_at TIMESTAMP
);

-- 进化日志（系统自我进化的完整记录）
evolution_log (
    id UUID PRIMARY KEY,
    event_type VARCHAR(30),              -- "agent_upgrade" | "config_tuning" | "debt_resolved" | "new_capability"
    source VARCHAR(50),                  -- 触发源："auto_detect" | "user_report" | "scheduled_audit"
    description TEXT,
    before_state JSON,
    after_state JSON,
    rollback_possible BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP
);

-- 全局配置调优记录
config_tuning_history (
    id UUID PRIMARY KEY,
    config_path VARCHAR(200),            -- "agents.defaults.model.fallbacks"
    old_value JSON,
    new_value JSON,
    reason TEXT,
    performance_impact JSON,             -- 调优后的性能变化统计
    tuned_at TIMESTAMP
);
```

**总架构师核心能力**:

| 能力 | 说明 | 触发方式 |
|------|------|---------|
| **健康监控** | 实时扫描所有Agent的日志/性能/错误率 | 定时（每小时） |
| **缺陷发现** | 自动识别类似 DEFECTS_AND_DEBT 的技术债 | 定时（每日） |
| **架构建议** | 基于运行时数据提出架构改进提案 | 事件驱动 |
| **自动修复** | 对低风险配置自动优化（如过期模型替换） | 自动 |
| **进化推演** | 模拟架构变更影响（"如果加Redis缓存，QPS提升多少？"） | 按需 |
| **知识蒸馏** | 从运行日志中提炼最佳实践，更新系统文档 | 定时（每周） |

**架构师审视已发现的缺陷（基于 DEFECTS_AND_DEBT.md）**:
```
🔴 HelpAgent数据存内存      → 提案：迁移到DB持久化（auto_apply=true）
🔴 LeaderboardAgent无持久化 → 提案：使用Redis Sorted Set替代dict
🔴 6/12 Agent零日志          → 提案：注入log_execution到所有Agent
🟡 LLM无熔断器               → 提案：实现Circuit Breaker模式
🟡 TutorView 457行          → 提案：拆分为4个组件
🟢 home_zone零逻辑           → 已纳入RPG系统设计（本文档）
```

**API 端点**:
```
GET  /api/v1/architect/health          # 系统健康仪表盘
GET  /api/v1/architect/proposals       # 架构改进提案列表
POST /api/v1/architect/proposals/{id}/approve  # 批准提案
POST /api/v1/architect/audit           # 手动触发全系统审计
GET  /api/v1/architect/evolution-log   # 进化日志
GET  /api/v1/architect/recommendations # AI优化建议
```

**Agent 规划**: `ArchitectAgent` — 系统监控、架构进化、自动优化

---

## 📊 数据模型总览（新增/变更）

### 变更表
| 表名 | 变更 |
|------|------|
| `lawa_profiles` | +character_class, +xp, +level, +talent_points, +skill_tree, +title, +avatar_config |
| `home_zone` | 保留兼容，但逻辑迁移到 `user_zones.current_zone_id` |

### 新增表（21张）
1. `language_zones` — 语言区域
2. `zone_nodes` — 区域内场景
3. `zone_connections` — 区域通道
4. `quest_templates` — 任务模板
5. `user_quests` — 用户任务实例
6. `dungeon_instances` — 副本实例
7. `language_guilds` — 公会
8. `guild_members` — 公会成员
9. `guild_quests` — 公会任务
10. `interguild_wars` — 公会竞技
11. `item_definitions` — 物品定义
12. `user_inventory` — 用户物品栏
13. `crafting_recipes` — 合成配方
14. `achievements` — 成就定义
15. `user_achievements` — 用户成就
16. `collection_sets` — 收藏套装
17. `milestone_stories` — 里程碑剧情
18. `system_health_snapshots` — 系统健康监控
19. `architecture_proposals` — 架构改进提案
20. `evolution_log` — 系统进化日志
21. `config_tuning_history` — 配置调优记录

---

## 🤖 Agent 扩展计划

现有 12 个 Agent → 扩展为 **18 个 Agent**：

| # | Agent | 职责 | 状态 |
|---|-------|------|------|
| 1 | AssessmentAgent | 语言评估 | ✅ 已有 |
| 2 | CompanionAgent | AI 伴读 | ✅ 已有 |
| 3 | PlanAgent | 学习规划 | ✅ 已有 |
| 4 | PersonaAgent | 用户画像 | ✅ 已有 |
| 5 | KnowledgeAgent | 知识库 | ✅ 已有 |
| 6 | CoinAgent | 金币经济 | ✅ 已有 |
| 7 | MatchAgent | 用户匹配 | ✅ 已有 |
| 8 | LeaderboardAgent | 排行榜 | ✅ 已有 |
| 9 | TaskAgent | 任务市场 | ✅ 已有 |
| 10 | HelpAgent | 社区求助 | ✅ 已有 |
| 11 | TutorAgent | AI 导师 | ✅ 已有 |
| 12 | CICDAgent | CI/CD | ✅ 已有 |
| **13** | **CharacterAgent** | **角色成长/经验/等级** | 🆕 新增 |
| **14** | **QuestAgent** | **任务/副本管理** | 🆕 新增 |
| **15** | **GuildAgent** | **公会/社交** | 🆕 新增 |
| **16** | **InventoryAgent** | **装备/道具/合成** | 🆕 新增 |
| **17** | **AchievementAgent** | **成就/收藏/剧情** | 🆕 新增 |
| **18** | **ArchitectAgent** | **系统监督/优化/进化** | 🆕 新增 |

---

## 🔗 API 端点总览（新增）

```
/api/v1/world/*          → WorldAgent / CharacterAgent
/api/v1/quests/*         → QuestAgent
/api/v1/dungeons/*       → QuestAgent
/api/v1/guilds/*         → GuildAgent
/api/v1/inventory/*      → InventoryAgent
/api/v1/shop/*           → InventoryAgent
/api/v1/achievements/*   → AchievementAgent
/api/v1/collections/*    → AchievementAgent
/api/v1/stories/*        → AchievementAgent
/api/v1/character/*      → CharacterAgent
/api/v1/architect/*      → ArchitectAgent
```

---

## 🧱 迁移路径（从现有 home_zone 到完整 RPG）

### Phase 0: 兼容保留（Day 1）
- `home_zone` 字段保留，但改为只读
- 新增 `user_zones` 关联表存储真实位置
- 原有数据自动迁移：home_zone → 匹配 language_zones.code

### Phase 1: 基础设施（Week 1）
- 创建 12+ 张新表
- 扩展 lawa_profiles（character_class, xp, level, ...）
- 开发 WorldAgent + CharacterAgent
- 种子数据：首批 2 个语言区域（华夏区、英美区）+ 20 个场景节点

### Phase 2: 核心循环（Week 2~3）
- XP 系统上线
- 日常任务系统
- 等级提升解锁机制

### Phase 3: 社交 + 副本（Week 4~5）
- 公会系统
- 副本/raid 系统
- 公会战

### Phase 4: 经济闭环（Week 6）
- 装备/道具系统
- 合成系统
- 商店

### Phase 5: 内容丰富（Week 7+）
- 成就体系完善
- 收藏套装
- 里程碑剧情（LLM 生成）
- 各语言区域特色内容

---

## 🎯 成功指标

| 指标 | 基准 | 目标 | 验证方式 |
|------|------|------|---------|
| 日均学习时间 | 20min | 30min（+50%） | 学习日志 |
| 7 日留存率 | 40% | 60% | 用户活跃统计 |
| 公会参与率 | N/A | 40% | 公会成员数 / 总用户数 |
| 任务完成率 | N/A | 70% | 接取任务 vs 完成任务 |
| 装备/道具交易 | N/A | 日活 30% | 交易流水 |

---

## 🧠 关键设计原则

1. **语言学习第一**：所有 RPG 机制必须服务于语言学习效果，不搞纯游戏化
2. **渐进式复杂度**：新手期保持简单（Lv1 只看到日常任务 + 一个区域），深度玩家才能看到全部系统
3. **可选深度**：不强制参与 RPG（可以只用基础学习功能），但深度参与者获得额外奖励
4. **文化真实性**：区域/场景/任务必须具有真实文化背景（如英美区=维多利亚蒸汽朋克风格）
5. **防沉迷设计**：每日 XP 上限、学习时长健康提醒（副本无限制，由在线总架构师动态监控）
6. **零破坏迁移**：不影响现有功能，RPG 作为可选增强层

---

## 📋 会议行动项（等待 Ke 确认）

| # | 行动 | 负责人 | 预计工时 |
|---|------|--------|---------|
| 1 | Ke 确认架构设计方向 | Ke | — |
| 2 | 细化数据模型（SQLAlchemy ORM） | 达子 | 4h |
| 3 | 设计首批种子内容（区域/任务/装备） | 达子 + Ke | 2h |
| 4 | 更新 SPRINT 计划，插入 RPG Sprint | 达子 | 2h |
| 5 | 开发 CharacterAgent + WorldAgent | 达子 | 8h |
| 6 | 数据库迁移脚本（alembic） | 达子 | 3h |

---

*设计人：达子 🦝 | 基于 LAWA 3 天冲刺经验 + DEFECTS_AND_DEBT.md 建议 | 等待 Ke 确认后开始实施*
