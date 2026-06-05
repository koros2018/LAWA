"""
LAWA PlanAgent — 学习规划Agent

功能：
- 基于用户画像和评估结果生成周/日学习计划
- 每日任务生成（个性化+可执行）
- 动态调整（根据进展调整难度和内容）
- 语言场景推荐
"""
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from src.agent.base_agent import BaseAgent
from src.config import settings
from src.services.llm_service import llm_service
from src.services.level_mapper import LEVEL_NUMERIC, get_level_gap, CEFR_DESCRIPTORS, HSK_DESCRIPTORS

PLAN_SYSTEM_PROMPT = """You are a language learning curriculum designer. Based on a learner's profile, assessment results, and goals, you create personalized weekly learning plans and daily tasks.

Your plans should be:
1. **Specific** — Concrete activities, not vague suggestions
2. **Achievable** — Realistic for the learner's level and time availability  
3. **Progressive** — Build from easier to harder within the week
4. **Balanced** — Cover multiple skills (grammar, vocabulary, reading, writing, speaking)
5. **Engaging** — Use topics the learner is interested in

Output valid JSON only."""

WEEKLY_PLAN_PROMPT = """Create a 7-day learning plan for this language learner:

**Language**: {learn_lang} (native: {native_lang})
**Current Level**: {level}
**Target Level**: {target_level}
**Learning Style**: {learning_style}
**Strengths**: {strengths}
**Weaknesses**: {weaknesses}
**Interests**: {interests}
**Available Time**: {daily_minutes} minutes/day
**Best Study Time**: {best_time}

Generate a weekly plan as JSON:
{{
  "week_overview": "This week's focus is...",
  "weekly_goals": ["goal 1", "goal 2", "goal 3"],
  "days": [
    {{
      "day": 1,
      "theme": "Grammar Foundations",
      "tasks": [
        {{
          "type": "grammar_exercise",
          "title": "Present Perfect vs Past Simple",
          "description": "Complete 15 fill-in-the-blank exercises...",
          "estimated_minutes": 15,
          "difficulty": "medium",
          "materials": "online exercises, textbook pages 45-48"
        }}
      ]
    }}
  ],
  "weekend_challenge": {{
    "title": "...",
    "description": "...",
    "reward_coins": 10
  }}
}}"""

DAILY_TASK_PROMPT = """Generate {count} specific daily tasks for this learner:

**Language**: {learn_lang}
**Level**: {level}
**Focus Areas**: {focus_areas}
**Learning Style**: {learning_style}
**Today's Theme**: {theme}

Tasks should be short (10-20 min each), actionable, and varied in skill type.
Include at least one speaking/pronunciation task and one writing task.

Return JSON:
{{
  "tasks": [
    {{
      "type": "vocabulary|grammar|reading|writing|speaking|listening|review",
      "title": "Task title",
      "instructions": "Detailed instructions...",
      "estimated_minutes": 15,
      "difficulty": "easy|medium|hard",
      "skill": "grammar",
      "completion_criteria": "How to know when done"
    }}
  ]
}}"""


class PlanAgent(BaseAgent):
    """学习规划Agent"""

    def __init__(self):
        super().__init__("PlanAgent")
        self.requires_persistence = False  # 纯计算
        self.requires_persistence = False  # 纯计算 Agent，无需 DB

    async def execute(self, payload: dict) -> dict:
        """
        payload:
        {
            "action": "generate_weekly_plan | generate_daily_tasks | adjust_plan",
            "user_id": "...",
            ...
        }
        """
        action = payload.get("action", "generate_weekly_plan")
        handlers = {
            "generate_weekly_plan": self.generate_weekly_plan,
            "generate_daily_tasks": self.generate_daily_tasks,
            "adjust_plan": self.adjust_plan,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    async def generate_weekly_plan(self, payload: dict) -> dict:
        """生成7天学习计划"""
        learn_lang = payload.get("learn_lang", "en")
        level = payload.get("level", "B1")
        target_level = payload.get("target_level", "B2")
        weaknesses = payload.get("weaknesses", [])
        interests = payload.get("interests", ["daily_life"])

        # 本地生成基础计划
        plan = self._local_weekly_plan(learn_lang, level, target_level, weaknesses, interests)

        # LLM增强
        try:
            prompt = WEEKLY_PLAN_PROMPT.format(
                learn_lang=learn_lang,
                native_lang=payload.get("native_lang", "zh"),
                level=level,
                target_level=target_level,
                learning_style=str(payload.get("learning_style", {})),
                strengths=", ".join(payload.get("strengths", [])),
                weaknesses=", ".join(weaknesses),
                interests=", ".join(interests),
                daily_minutes=payload.get("daily_minutes", 30),
                best_time=payload.get("best_time", "evening"),
            )
            prompt = prompt.replace("{{", "{").replace("}}", "}")

            messages = [
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            result = await llm_service.chat_json(messages=messages, task="planning")
            plan = {**plan, **result}
        except Exception as e:
            logger.warning(f"LLM生成周计划失败: {e}")

        # 计算到目标等级所需周数
        gap = get_level_gap(level, target_level)
        estimated_weeks = max(gap * 8, 4)  # 每级约8周

        return {
            "plan": plan,
            "meta": {
                "current_level": level,
                "target_level": target_level,
                "level_gap": gap,
                "estimated_weeks_to_target": estimated_weeks,
                "lang": learn_lang,
            },
        }

    async def generate_daily_tasks(self, payload: dict) -> dict:
        """生成今日任务列表"""
        learn_lang = payload.get("learn_lang", "en")
        level = payload.get("level", "B1")
        focus_areas = payload.get("focus_areas", ["grammar", "vocabulary"])
        theme = payload.get("theme", "Daily Practice")
        count = payload.get("count", 3)

        # 本地生成
        tasks = self._local_daily_tasks(learn_lang, level, focus_areas, count)

        try:
            prompt = DAILY_TASK_PROMPT.format(
                count=count,
                learn_lang=learn_lang,
                level=level,
                focus_areas=", ".join(focus_areas),
                learning_style=str(payload.get("learning_style", {})),
                theme=theme,
            )
            prompt = prompt.replace("{{", "{").replace("}}", "}")

            messages = [
                {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            result = await llm_service.chat_json(messages=messages, task="planning")
            tasks = result.get("tasks", tasks)
        except Exception as e:
            logger.warning(f"LLM生成每日任务失败: {e}")

        # 金币计算
        total_minutes = sum(t.get("estimated_minutes", 15) for t in tasks)
        potential_coins = min(total_minutes // 10, 12)

        return {
            "tasks": tasks,
            "total_minutes": total_minutes,
            "potential_coins": potential_coins,
            "date": payload.get("date", "today"),
        }

    async def adjust_plan(self, payload: dict) -> dict:
        """
        根据学习进展动态调整计划

        payload:
        {
            "current_plan": {...},
            "completion_stats": {"total_tasks": 7, "completed": 3, "avg_rating": 4.2, "total_minutes": 120},
            "weak_areas": ["grammar", "speaking"],
            "level": "B1",
        }
        """
        current_plan = payload.get("current_plan", {})
        stats = payload.get("completion_stats", {})
        weak_areas = payload.get("weak_areas", [])
        level = payload.get("level", "B1")

        total_tasks = stats.get("total_tasks", 7)
        completed = stats.get("completed", 0)
        avg_rating = stats.get("avg_rating", 3)
        total_minutes = stats.get("total_minutes", 0)

        completion_rate = completed / max(total_tasks, 1)
        adjustments = []

        # ── 1. 完成率分析 → 调整强度 ──
        if completion_rate < settings.plan_completion_low:
            adjustments.append({
                "type": "reduce_intensity",
                "reason": f"完成率仅 {completion_rate:.0%}，可能太忙或难度太高",
                "action": "减少每日任务数 2~3 个，降低单任务时长到 10~15 分钟",
            })
        elif completion_rate < settings.plan_completion_moderate:
            adjustments.append({
                "type": "moderate",
                "reason": f"完成率 {completion_rate:.0%}，节奏偏慢",
                "action": "保持当前节奏，将未完成任务优先级提升",
            })
        elif completion_rate >= settings.plan_completion_high:
            adjustments.append({
                "type": "increase_challenge",
                "reason": f"完成率 {completion_rate:.0%}，可以加码",
                "action": "增加每日任务 1~2 个，或提升到下一等级难度",
            })

        # ── 2. 弱项聚焦
        if weak_areas:
            adjustments.append({
                "type": "focus_weak_areas",
                "reason": f"最新弱项: {', '.join(weak_areas)}",
                "action": f"未来3天任务增加 {', '.join(weak_areas[:2])} 练习",
                "target_areas": weak_areas,
            })

        # ── 3. 评分分析 → 调整风格
        if avg_rating < settings.plan_rating_low:
            adjustments.append({
                "type": "change_style",
                "reason": f"任务平均评分 {avg_rating}/5，可能不感兴趣",
                "action": "尝试更多互动型任务（游戏/对话/场景）替代纯文本练习",
            })
        elif avg_rating >= settings.plan_rating_high:
            adjustments.append({
                "type": "keep_style",
                "reason": f"任务平均评分 {avg_rating}/5，当前方式很适合",
                "action": "保持当前任务类型和学习风格",
            })

        # ── 4. 时间分析
        target_daily = current_plan.get("meta", {}).get("daily_minutes", 30)
        actual_daily = total_minutes / max(total_tasks, 1)
        if actual_daily > target_daily * settings.plan_time_overflow_ratio:
            adjustments.append({
                "type": "time_overflow",
                "reason": f"实际日均 {actual_daily:.0f}min > 目标 {target_daily}min",
                "action": "超出预期投入，建议保持并考虑提升目标等级",
            })

        # ── 5. 调整后的计划元数据
        adjusted_meta = {
            **current_plan.get("meta", {}),
            "adjusted_at": datetime.now(timezone.utc).isoformat(),
            "completion_rate": round(completion_rate, 2),
            "adjustment_count": len(adjustments),
        }

        logger.info(
            f"计划调整: completion={completion_rate:.0%} | "
            f"adjustments={len(adjustments)} | level={level}"
        )

        return {
            "adjusted_meta": adjusted_meta,
            "adjustments": adjustments,
            "completion_rate": round(completion_rate, 2),
            "recommendation": adjustments[0]["action"] if adjustments else "继续保持当前学习节奏 👍",
        }

    # ── 本地计划生成 ──
    def _local_weekly_plan(self, lang: str, level: str, target: str, weaknesses: list, interests: list) -> dict:
        """本地生成7天计划骨架"""
        gap = get_level_gap(level, target)
        focus = weaknesses if weaknesses else ["grammar", "vocabulary", "speaking"]

        themes = ["Grammar Focus", "Vocabulary Building", "Reading Practice", "Writing Workshop",
                  "Speaking & Listening", "Review & Consolidation", "Challenge Day"]

        days = []
        for i, theme in enumerate(themes):
            tasks = self._generate_day_tasks(lang, level, theme, focus, interests)
            days.append({
                "day": i + 1,
                "theme": theme,
                "tasks": tasks,
            })

        return {
            "week_overview": f"This week focuses on strengthening {' and '.join(focus[:3])}. Gap from {level} to {target}: {gap} level(s).",
            "weekly_goals": [
                f"Complete 7 days of focused practice",
                f"Learn 20+ new {'words' if lang == 'en' else '汉字'}",
                f"Improve {focus[0] if focus else 'overall'} by at least one sub-level",
            ],
            "days": days,
            "weekend_challenge": {
                "title": "Weekend Language Mission",
                "description": f"Write a short {'essay' if lang == 'en' else '短文'} about {interests[0] if interests else 'your week'} and have AI review it.",
                "reward_coins": 10,
            },
        }

    def _generate_day_tasks(self, lang: str, level: str, theme: str, focus: list, interests: list) -> list:
        """为一天生成任务列表"""
        task_templates = {
            "Grammar Focus": [
                {"type": "grammar_exercise", "title": "Grammar Drill", "estimated_minutes": 15, "difficulty": "medium"},
                {"type": "writing", "title": "Apply Grammar in Writing", "estimated_minutes": 15, "difficulty": "medium"},
            ],
            "Vocabulary Building": [
                {"type": "vocabulary", "title": "New Words Learning", "estimated_minutes": 15, "difficulty": "easy"},
                {"type": "reading", "title": "Reading with New Vocabulary", "estimated_minutes": 15, "difficulty": "medium"},
            ],
            "Reading Practice": [
                {"type": "reading", "title": f"Read about {interests[0] if interests else 'current events'}", "estimated_minutes": 20, "difficulty": "medium"},
                {"type": "vocabulary", "title": "Extract & Learn New Words", "estimated_minutes": 10, "difficulty": "easy"},
            ],
            "Writing Workshop": [
                {"type": "writing", "title": "Write a Short Composition", "estimated_minutes": 20, "difficulty": "hard"},
                {"type": "grammar_exercise", "title": "Self-Correction Exercise", "estimated_minutes": 10, "difficulty": "medium"},
            ],
            "Speaking & Listening": [
                {"type": "speaking", "title": "Shadow Speaking Practice", "estimated_minutes": 15, "difficulty": "medium"},
                {"type": "listening", "title": "Listen & Summarize", "estimated_minutes": 15, "difficulty": "medium"},
            ],
            "Review & Consolidation": [
                {"type": "review", "title": "Week Review Quiz", "estimated_minutes": 15, "difficulty": "easy"},
                {"type": "vocabulary", "title": "Spaced Repetition Review", "estimated_minutes": 10, "difficulty": "easy"},
            ],
            "Challenge Day": [
                {"type": "writing", "title": "Extended Writing Challenge", "estimated_minutes": 25, "difficulty": "hard"},
                {"type": "speaking", "title": "Record a 2-Minute Speech", "estimated_minutes": 15, "difficulty": "hard"},
            ],
        }

        base_tasks = task_templates.get(theme, task_templates["Grammar Focus"])
        for t in base_tasks:
            t["skill"] = t.get("type", "grammar")
            t["instructions"] = f"Complete the {t['title'].lower()} at {level} level."
            t["completion_criteria"] = "Task completed and self-reviewed"

        return base_tasks

    def _local_daily_tasks(self, lang: str, level: str, focus_areas: list, count: int) -> list:
        """本地生成每日任务"""
        all_tasks = []
        for area in focus_areas[:count]:
            all_tasks.append({
                "type": area,
                "title": f"Daily {area.capitalize()} Practice",
                "instructions": f"Practice {area} at {level} level for 15 minutes.",
                "estimated_minutes": 15,
                "difficulty": "medium",
                "skill": area,
                "completion_criteria": "15 minutes of focused practice completed",
            })
        return all_tasks[:count]
