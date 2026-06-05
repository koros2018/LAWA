"""
LAWA PersonaAgent — 用户画像Agent

功能：
- 学习风格识别（VARK模型：Visual/Auditory/Reading/Kinesthetic）
- 兴趣领域标签（从评估表现和问卷提取）
- 服务能力标签（can_help：用户能帮别人什么）
- 弱项诊断（从评估报告中提取）
- AI导师画像初始化
"""
from typing import Optional
from loguru import logger
from src.agent.base_agent import BaseAgent
from src.config import settings
from src.services.llm_service import llm_service
from src.services.level_mapper import LEVEL_NUMERIC, get_level_gap

PERSONA_SYSTEM_PROMPT = """You are a learning style analyst. Based on a user's language assessment results and their responses, you identify:

1. **Learning Style (VARK)** — Visual, Auditory, Reading/Writing, Kinesthetic (can be mixed)
2. **Strengths & Weaknesses** — What the user excels at and struggles with
3. **Interest Tags** — Topics the user is passionate about (tech, travel, business, culture, etc.)
4. **Learning Habits** — Time preferences, consistency, motivation level
5. **Service Capabilities** — What the user can help OTHERS with (based on their native language strengths)

Output valid JSON only."""

PERSONA_ANALYSIS_PROMPT = """Analyze this language learner's profile:

**Language**: {lang} ({native_lang} → {learn_lang})
**Level**: {level}
**Assessment Results**: {assessment_summary}
**Dimension Scores**: {dimension_scores}

**Questionnaire Responses** (if any): {questionnaire}

Based on this data, return a comprehensive learner persona as JSON:
{{
  "learning_style": {{
    "primary": "reading_writing",
    "secondary": "visual",
    "vark_scores": {{"visual": 3, "auditory": 2, "reading_writing": 4, "kinesthetic": 1}},
    "explanation": "..."
  }},
  "strengths": ["grammar accuracy", "reading comprehension"],
  "weaknesses": ["spoken fluency", "listening comprehension"],
  "interests": ["technology", "travel", "business"],
  "learning_habits": {{
    "best_time": "morning",
    "session_length_minutes": 25,
    "consistency_level": "medium",
    "motivation": "career advancement"
  }},
  "service_capabilities": ["writing_correction_zh", "grammar_explanation_zh", "beginner_tutoring_zh"],
  "persona_summary": "A structured learner who prefers reading and systematic study..."
}}"""

TUTOR_INIT_PROMPT = """Initialize an AI language tutor profile for this learner:

**Learner Profile**: {persona_summary}
**Language**: {learn_lang}
**Current Level**: {level}
**Weak Areas**: {weaknesses}
**Learning Style**: {learning_style}

Create a tutor persona that will be the BEST match for this learner. The tutor should have:
1. A teaching style that complements the learner's weaknesses
2. Personality traits that match the learner's style
3. Areas of expertise
4. Default teaching strategies

Return JSON:
{{
  "tutor_name": "a fitting name",
  "teaching_style": "patient_explainer|drill_master|conversationalist|storyteller|grammar_nerd",
  "personality": ["encouraging", "structured", "humorous"],
  "expertise": ["grammar", "business_english", ...],
  "default_strategies": ["error_correction_with_explanation", "scenario_based_learning", ...],
  "tutor_intro": "Short introduction the tutor would say to the learner."
}}"""


class PersonaAgent(BaseAgent):
    """用户画像Agent"""

    def __init__(self):
        super().__init__("PersonaAgent")
        self.requires_persistence = False  # 纯计算
        self.requires_persistence = False  # 纯计算 Agent，无需 DB

    async def execute(self, payload: dict) -> dict:
        """
        payload:
        {
            "action": "analyze_persona | init_tutor | update_persona",
            "user_id": "...",
            "lang": "en",
            "native_lang": "zh",
            "learn_lang": "en",
            "level": "B1",
            "assessment_summary": "...",
            "dimension_scores": {...},
            "questionnaire": {...}
        }
        """
        action = payload.get("action", "analyze_persona")
        handlers = {
            "analyze_persona": self.analyze_persona,
            "init_tutor": self.init_tutor,
            "update_persona": self.update_persona,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    async def analyze_persona(self, payload: dict) -> dict:
        """分析用户画像"""
        lang = payload.get("lang", "en")
        level = payload.get("level", "B1")
        assessment_summary = payload.get("assessment_summary", "No assessment data yet")
        dimension_scores = payload.get("dimension_scores", {})

        # 本地推断（LLM不可用时的兜底）
        local_persona = self._local_persona_inference(level, dimension_scores, lang)

        # LLM增强分析
        try:
            prompt = PERSONA_ANALYSIS_PROMPT.format(
                lang=lang,
                native_lang=payload.get("native_lang", "zh"),
                learn_lang=payload.get("learn_lang", "en"),
                level=level,
                assessment_summary=str(assessment_summary)[:500],
                dimension_scores=str(dimension_scores)[:500],
                questionnaire=str(payload.get("questionnaire", {})),
            )
            # 双花括号转义
            prompt = prompt.replace("{{", "{").replace("}}", "}")

            messages = [
                {"role": "system", "content": PERSONA_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            result = await llm_service.chat_json(messages=messages, task="assessment")
            # 合并LLM结果和本地推断
            persona = {**local_persona, **result}
        except Exception as e:
            logger.warning(f"LLM画像分析失败，使用本地推断: {e}")
            persona = local_persona

        return {"persona": persona}

    async def init_tutor(self, payload: dict) -> dict:
        """初始化AI导师画像"""
        persona_summary = payload.get("persona_summary", "")
        learn_lang = payload.get("learn_lang", "en")
        level = payload.get("level", "B1")
        weaknesses = payload.get("weaknesses", [])
        learning_style = payload.get("learning_style", {})

        # 本地默认导师
        tutor = self._default_tutor(learn_lang, level, weaknesses)

        try:
            prompt = TUTOR_INIT_PROMPT.format(
                persona_summary=str(persona_summary)[:300],
                learn_lang=learn_lang,
                level=level,
                weaknesses=", ".join(weaknesses) if weaknesses else "unknown",
                learning_style=str(learning_style),
            )
            prompt = prompt.replace("{{", "{").replace("}}", "}")

            messages = [
                {"role": "system", "content": "You create personalized AI tutor profiles. Output JSON only."},
                {"role": "user", "content": prompt},
            ]

            result = await llm_service.chat_json(messages=messages, task="planning")
            tutor = {**tutor, **result}
        except Exception as e:
            logger.warning(f"LLM导师初始化失败: {e}")

        # 导师向量初始化（留到 ChromaDB 集成）
        tutor["tutor_vector_seed"] = {
            "teaching_style": tutor.get("teaching_style", ""),
            "expertise": tutor.get("expertise", []),
            "level": level,
            "lang": learn_lang,
        }

        return {"tutor": tutor}

    async def update_persona(self, payload: dict) -> dict:
        """
        增量更新用户画像（学习过程中持续演进）

        payload:
        {
            "existing_persona": {...},           # 当前画像
            "new_dimension_scores": {...},      # 新评估维度分数
            "new_level": "B2",                  # 新等级（如有提升）
            "study_minutes_delta": 30,           # 新增学习分钟数
            "session_feedback": {...},           # 伴读/任务反馈
        }
        """
        existing = payload.get("existing_persona", {})
        new_scores = payload.get("new_dimension_scores", {})
        new_level = payload.get("new_level")
        study_delta = payload.get("study_minutes_delta", 0)

        # ── 1. 合并强弱项 ──
        strengths = list(existing.get("strengths", []))
        weaknesses = list(existing.get("weaknesses", []))

        for dim, data in new_scores.items():
            score = data.get("average_score", 5) if isinstance(data, dict) else data
            if score >= settings.persona_strength_threshold and dim not in strengths:
                strengths.append(dim)
                if dim in weaknesses:
                    weaknesses.remove(dim)
            elif score < settings.persona_weakness_threshold and dim not in weaknesses:
                weaknesses.append(dim)
                if dim in strengths:
                    strengths.remove(dim)

        # ── 2. 等级更新 ──
        current_level = new_level or existing.get("current_level", "A1")
        level_num = LEVEL_NUMERIC.get(current_level, 1)

        # ── 3. 学习风格演进 ──
        style = existing.get("learning_style", {})
        if level_num >= 4:
            # 中高级 → 更多听说
            style = {"primary": "auditory", "secondary": "kinesthetic"}
        elif level_num >= 2:
            style = {"primary": "reading_writing", "secondary": "auditory"}
        else:
            style = {"primary": "visual", "secondary": "reading_writing"}

        # ── 4. 累计学习时间 ──
        total_minutes = existing.get("total_study_minutes", 0) + study_delta

        # ── 5. 技能树更新 ──
        skill_tree = existing.get("skill_tree", {})
        for dim in strengths:
            if dim in skill_tree:
                skill_tree[dim] = min(skill_tree[dim] + 1, 10)
            else:
                skill_tree[dim] = 1

        # ── 6. 兴趣标签合并 ──
        interests = list(existing.get("interests", []))
        new_interests = payload.get("new_interests", [])
        for interest in new_interests:
            if interest not in interests:
                interests.append(interest)

        updated = {
            **existing,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "current_level": current_level,
            "learning_style": style,
            "total_study_minutes": total_minutes,
            "skill_tree": skill_tree,
            "interests": interests,
        }

        # ── 变更摘要 ──
        changes = []
        if strengths != existing.get("strengths", []):
            changes.append(f"strengths updated: {set(strengths) - set(existing.get('strengths', []))}")
        if weaknesses != existing.get("weaknesses", []):
            changes.append(f"weaknesses updated")
        if new_level and new_level != existing.get("current_level"):
            changes.append(f"level: {existing.get('current_level')} → {new_level}")
        if study_delta > 0:
            changes.append(f"+{study_delta}min study time")
        if new_interests:
            changes.append(f"interests +{new_interests}")

        logger.info(f"画像更新: {len(changes)} changes | level={current_level} | strengths={len(strengths)} | total_min={total_minutes}")

        return {
            "persona": updated,
            "changes": changes,
            "changed": len(changes) > 0,
        }

    # ── 本地推断 ──
    def _local_persona_inference(self, level: str, dimension_scores: dict, lang: str) -> dict:
        """基于评估分数本地推断画像"""
        # 弱项识别
        weak_dims = []
        strong_dims = []
        for dim, data in dimension_scores.items():
            score = data.get("average_score", 5) if isinstance(data, dict) else 5
            if score < settings.persona_weakness_threshold:
                weak_dims.append(dim)
            if score >= settings.persona_strength_threshold:
                strong_dims.append(dim)

        # 等级推断学习风格
        level_num = LEVEL_NUMERIC.get(level, 3)
        if level_num <= 2:
            style = {"primary": "visual", "secondary": "reading_writing"}
        elif level_num <= 4:
            style = {"primary": "reading_writing", "secondary": "auditory"}
        else:
            style = {"primary": "auditory", "secondary": "kinesthetic"}

        # 服务能力推断（基于母语水平）
        native = lang
        if native == "zh":
            can_help = ["writing_correction_zh", "grammar_explanation_zh", "beginner_chinese_tutoring"]
        else:
            can_help = ["writing_correction_en", "pronunciation_coaching", "conversation_practice_en"]

        return {
            "learning_style": style,
            "strengths": strong_dims,
            "weaknesses": weak_dims,
            "interests": ["daily_life", "travel"],
            "learning_habits": {
                "best_time": "evening",
                "session_length_minutes": 20,
                "consistency_level": "medium",
                "motivation": "personal_growth",
            },
            "service_capabilities": can_help,
            "persona_summary": f"Level {level} {lang} learner. Strengths: {', '.join(strong_dims) or 'none yet'}. Needs improvement in: {', '.join(weak_dims) or 'multiple areas'}.",
        }

    def _default_tutor(self, learn_lang: str, level: str, weaknesses: list) -> dict:
        """默认AI导师配置"""
        return {
            "tutor_name": "Alex" if learn_lang == "en" else "小明",
            "teaching_style": "patient_explainer",
            "personality": ["encouraging", "structured", "friendly"],
            "expertise": weaknesses or ["grammar", "vocabulary"],
            "default_strategies": ["error_correction_with_explanation", "scenario_based_learning"],
            "tutor_intro": f"Hi! I'm your personal language tutor. I see you're at {level} level — let's work together to improve your {', '.join(weaknesses) if weaknesses else 'overall skills'}!",
        }
