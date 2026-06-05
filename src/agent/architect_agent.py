"""
ArchitectAgent —— 总架构师（18号Agent）

监督整个 LAWA 系统运行状态，定期巡检，发现缺口，提出优化建议。
"""
import os
import re
import logging
from datetime import datetime, timezone
from sqlalchemy import text, select, func
from src.database import AsyncSessionLocal, Base
from src.agent.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """系统总架构师 —— 监督/优化/进化"""

    def __init__(self):
        super().__init__(name="ArchitectAgent")

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "dashboard")
        handlers = {
            "health": self.health_check,
            "dashboard": self.dashboard,
            "audit": self.code_audit,
            "report": self.full_report,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        try:
            result = await handler(payload)
            self.log_execution(payload, result)
            return result
        except Exception as e:
            logger.error(f"ArchitectAgent error: {e}")
            return {"error": str(e)}

    # ═══════════════════════════════════════
    #  健康检查
    # ═══════════════════════════════════════

    async def health_check(self, payload: dict) -> dict:
        """检查系统各组件健康状态"""
        issues = []
        checks = {}

        # 1. 数据库连接
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "✅ 正常"
        except Exception as e:
            checks["database"] = f"❌ 异常: {e}"
            issues.append(f"数据库连接失败: {e}")

        # 2. 表完整性
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ))
                db_tables = {row[0] for row in result.fetchall() if not row[0].startswith("_")}

                code_tables = set(Base.metadata.tables.keys())
                missing_in_db = code_tables - db_tables
                extra_in_db = db_tables - code_tables - {"alembic_version"}

                checks["tables"] = {
                    "code_defined": len(code_tables),
                    "db_exists": len(db_tables),
                    "missing_in_db": sorted(missing_in_db),
                    "extra_in_db": sorted(extra_in_db),
                }
                if missing_in_db:
                    issues.append(f"代码定义了但DB中没有的表: {missing_in_db}")
        except Exception as e:
            checks["tables"] = f"❌ 无法检查: {e}"
            issues.append(f"表检查失败: {e}")

        # 3. 各表行数
        table_rows = {}
        try:
            async with AsyncSessionLocal() as session:
                for table_name in sorted(Base.metadata.tables.keys()):
                    try:
                        result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                        table_rows[table_name] = result.scalar()
                    except Exception:
                        table_rows[table_name] = -1  # 表不存在
        except Exception as e:
            table_rows = {"error": str(e)}

        checks["table_rows"] = table_rows

        # 4. Agent 文件检查
        agent_dir = os.path.join(os.path.dirname(__file__))
        agent_files = sorted(
            f for f in os.listdir(agent_dir)
            if f.endswith("_agent.py") and f != "__init__.py"
        )
        checks["agents"] = {
            "count": len(agent_files),
            "files": agent_files,
        }

        return {
            "status": "healthy" if not issues else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "issues": issues,
            "checks": checks,
        }

    # ═══════════════════════════════════════
    #  数据面板
    # ═══════════════════════════════════════

    async def dashboard(self, payload: dict) -> dict:
        """聚合各子系统的关键数据"""
        stats = {}
        async with AsyncSessionLocal() as session:
            # 用户
            stats["users"] = await self._count(session, "users")
            stats["profiles"] = await self._count(session, "lawa_profiles")

            # 学习
            stats["tasks"] = await self._count(session, "tasks")
            stats["task_submissions"] = await self._count(session, "task_submissions")
            stats["assessments"] = await self._count(session, "assessments")
            stats["companion_sessions"] = await self._count(session, "companion_sessions")

            # 经济
            stats["coin_transactions"] = await self._count(session, "coin_transactions")

            # 社区
            stats["help_requests"] = await self._count(session, "help_requests")
            stats["leaderboard_entries"] = await self._count(session, "leaderboard_entries")

            # RPG
            stats["quest_templates"] = await self._count(session, "quest_templates")
            stats["user_quests"] = await self._count(session, "user_quests")
            stats["language_guilds"] = await self._count(session, "guild_members")
            stats["guild_members"] = await self._count(session, "guild_members")
            stats["guild_tasks"] = await self._count(session, "guild_tasks")
            stats["equipment"] = await self._count(session, "equipment")
            stats["consumables"] = await self._count(session, "consumables")
            stats["user_inventory"] = await self._count(session, "user_inventory")
            stats["achievements"] = await self._count(session, "achievements")
            stats["user_achievements"] = await self._count(session, "user_achievements")

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
            "summary": self._dashboard_summary(stats),
        }

    # ═══════════════════════════════════════
    #  代码审查
    # ═══════════════════════════════════════

    async def code_audit(self, payload: dict) -> dict:
        """扫描代码库，发现潜在问题"""
        src_root = os.path.dirname(os.path.dirname(__file__))  # src/
        findings = {
            "todos": [],
            "agent_route_gaps": [],
            "summary": "",
        }

        # 1. 扫描 TODO/FIXME
        for root, dirs, files in os.walk(src_root):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                try:
                    with open(path) as fh:
                        for i, line in enumerate(fh, 1):
                            if re.search(r"#\s*(TODO|FIXME|HACK|XXX)", line):
                                rel = os.path.relpath(path, src_root)
                                findings["todos"].append({
                                    "file": rel, "line": i,
                                    "text": line.strip(),
                                })
                except Exception:
                    pass

        # 2. Agent vs Route 缺口
        agent_dir = os.path.join(src_root, "agent")
        route_dir = os.path.join(src_root, "routes")
        if os.path.isdir(agent_dir) and os.path.isdir(route_dir):
            agents = {
                f.replace("_agent.py", ""): f
                for f in os.listdir(agent_dir)
                if f.endswith("_agent.py") and f not in ("__init__.py", "base_agent.py")
            }

            # 从路由文件中提取引用的 Agent
            route_agents = set()
            for rf in os.listdir(route_dir):
                if not rf.endswith(".py") or rf == "__init__.py":
                    continue
                try:
                    with open(os.path.join(route_dir, rf)) as fh:
                        content = fh.read()
                    for ag in agents:
                        if ag in content.lower():
                            route_agents.add(ag)
                except Exception:
                    pass

            findings["agent_route_gaps"] = sorted(set(agents.keys()) - route_agents)

        # 3. 总结
        findings["summary"] = (
            f"发现 {len(findings['todos'])} 个 TODO, "
            f"{len(findings['agent_route_gaps'])} 个 Agent 未挂路由"
        )

        return findings

    # ═══════════════════════════════════════
    #  完整报告
    # ═══════════════════════════════════════

    async def full_report(self, payload: dict) -> dict:
        """生成 Markdown 格式的完整系统报告"""
        health = await self.health_check({})
        dash = await self.dashboard({})
        audit = await self.code_audit({})

        # 生成 Markdown
        md = self._build_markdown(health, dash, audit)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": health["status"],
            "issues": health["issues"],
            "todo_count": len(audit["todos"]),
            "gap_agents": audit["agent_route_gaps"],
            "markdown": md,
        }

    # ═══════════════════════════════════════
    #  helpers
    # ═══════════════════════════════════════

    async def _count(self, session, table: str) -> int:
        try:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            return result.scalar() or 0
        except Exception:
            return -1

    def _dashboard_summary(self, stats: dict) -> str:
        parts = []
        if stats.get("users", 0) > 0:
            parts.append(f"👥 {stats['users']} 用户")
        if stats.get("tasks", 0) > 0:
            parts.append(f"📋 {stats['tasks']} 任务")
        if stats.get("companion_sessions", 0) > 0:
            parts.append(f"💬 {stats['companion_sessions']} 对话")
        if stats.get("user_quests", 0) > 0:
            parts.append(f"⚔️ {stats['user_quests']} 副本")
        if stats.get("guild_members", 0) > 0:
            parts.append(f"🏰 {stats['language_guilds']} 公会")
        if stats.get("coin_transactions", 0) > 0:
            parts.append(f"🪙 {stats['coin_transactions']} 金币流水")
        return " | ".join(parts) if parts else "暂无数据（需先运行种子数据）"

    def _build_markdown(self, health: dict, dash: dict, audit: dict) -> str:
        lines = [
            "# 🏗️ LAWA 系统巡检报告",
            f"**时间:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"**状态:** {health['status']}",
            "",
            "## 📊 数据面板",
            "",
        ]

        stats = dash.get("stats", {})
        # 分组展示
        groups = {
            "👤 用户": ["users", "profiles"],
            "📚 学习": ["tasks", "task_submissions", "assessments", "companion_sessions"],
            "🪙 经济": ["coin_transactions"],
            "🤝 社区": ["help_requests", "leaderboard_entries"],
            "🎮 RPG": [
                "quest_templates", "user_quests",
                "language_guilds", "guild_members", "guild_tasks",
                "equipment", "consumables", "user_inventory",
                "achievements", "user_achievements",
            ],
        }

        for group_name, keys in groups.items():
            lines.append(f"### {group_name}")
            for k in keys:
                v = stats.get(k, "?")
                icon = "⚠️" if v == -1 else ""
                lines.append(f"- **{k}:** {icon}{v}")
            lines.append("")

        # 问题
        issues = health.get("issues", [])
        if issues:
            lines.append("## ⚠️ 发现问题")
            for issue in issues:
                lines.append(f"- {issue}")
            lines.append("")

        # TODO
        todos = audit.get("todos", [])
        if todos:
            lines.append(f"## 📝 待办事项 ({len(todos)})")
            for t in todos[:20]:
                lines.append(f"- `{t['file']}:{t['line']}` {t['text']}")
            if len(todos) > 20:
                lines.append(f"- ...还有 {len(todos)-20} 个")
            lines.append("")

        # Agent 缺口
        gaps = audit.get("agent_route_gaps", [])
        if gaps:
            lines.append("## 🔌 未挂载路由的 Agent")
            for g in gaps:
                lines.append(f"- `{g}_agent.py`")
            lines.append("")

        # 架构规模
        agent_count = health.get("checks", {}).get("agents", {}).get("count", "?")
        table_count = len(health.get("checks", {}).get("table_rows", {}))
        lines.append("## 📐 架构规模")
        lines.append(f"- Agent: {agent_count} 个")
        lines.append(f"- 数据表: {table_count} 张")
        lines.append("")

        # 建议
        lines.append("## 💡 优化建议")
        suggestions = self._generate_suggestions(health, dash, audit)
        if suggestions:
            for s in suggestions:
                lines.append(f"- {s}")
        else:
            lines.append("- 系统运行良好，暂无优化建议 🎉")

        return "\n".join(lines)

    def _generate_suggestions(self, health: dict, dash: dict, audit: dict) -> list:
        suggestions = []

        # 数据库缺失表
        missing_tables = health.get("checks", {}).get("tables", {}).get("missing_in_db", [])
        if missing_tables:
            suggestions.append(
                f"🔴 数据库缺少 {len(missing_tables)} 张表，请运行 `alembic upgrade head`"
            )

        # Agent 未挂路由
        gaps = audit.get("agent_route_gaps", [])
        if gaps:
            suggestions.append(
                f"🟡 {len(gaps)} 个 Agent 未挂载路由: {', '.join(gaps)}"
            )

        # TODO 堆积
        todo_count = len(audit.get("todos", []))
        if todo_count > 5:
            suggestions.append(f"🟡 {todo_count} 个 TODO 待清理，建议分批处理")

        # 种子数据
        stats = dash.get("stats", {})
        if stats.get("users", 0) == 0:
            suggestions.append("🟡 无用户数据，请运行 `python scripts/seed.py`")

        return suggestions
