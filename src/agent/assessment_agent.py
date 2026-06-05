"""
LAWA AssessmentAgent — 多语言水平评估Agent

支持中英文双语言的CEFR/HSK自适应测试：
- 自适应出题（根据前一题表现调整难度）
- 多维度覆盖（语法/词汇/阅读/写作/汉字）
- LLM评分 + Majority Voting
- 结构化报告生成
"""
import uuid
import time
from typing import Optional
from datetime import datetime, timezone
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.base_agent import BaseAgent
from src.config import settings
from src.services.llm_service import llm_service
from src.services.level_mapper import (
    CEFRLevel, HSKLevel,
    CEFR_DESCRIPTORS, HSK_DESCRIPTORS,
    LEVEL_NUMERIC, ASSESSMENT_DIMENSIONS,
    DIMENSION_LABELS, hsk_to_cefr, cefr_to_hsk,
)
from src.services.assessment_prompts import (
    get_system_prompt, get_test_prompt, get_scoring_prompt, get_report_prompt,
)
from src.models.assessment import Assessment, AssessmentQuestion


class AssessmentAgent(BaseAgent):
    """多语言水平评估Agent"""

    def __init__(self):
        super().__init__("AssessmentAgent")
        self.timeout_seconds = 120  # LLM 出题/评分需要更长时间
        self.default_questions_per_dimension = settings.assess_questions_per_dimension
        self.min_questions_for_report = settings.assess_min_questions_for_report

    async def execute(self, payload: dict) -> dict:
        """
        执行评估流程

        payload:
        {
            "action": "start_assessment | generate_question | submit_answer | generate_report",
            "user_id": "...",
            "lang": "en" | "zh",
            "assessment_id": "..." (后续步骤),
            "dimension": "grammar",            (generate_question)
            "current_level_estimate": "B1",    (generate_question)
            "question_id": "...",              (submit_answer)
            "db": AsyncSession (可选),          # DB会话，用于持久化
            "user_answer": "...",              (submit_answer)
        }
        """
        action = payload.get("action", "start_assessment")

        handlers = {
            "start_assessment": self.start_assessment,
            "generate_question": self.generate_question,
            "submit_answer": self.submit_answer,
            "generate_report": self.generate_report,
        }

        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}

        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    # ── 1. 启动评估 ──
    async def start_assessment(self, payload: dict) -> dict:
        """
        创建评估会话，返回初始评估信息

        返回：
        {
            "assessment_id": "uuid",
            "lang": "en",
            "dimensions": ["grammar", "vocabulary", "reading", "writing"],
            "current_level_estimate": "B1",  # 初始锚定
            "next_dimension": "grammar",
            "total_questions_planned": 12
        }
        """
        lang = payload.get("lang", "en")
        user_id = payload.get("user_id")
        db: Optional[AsyncSession] = payload.get("db")

        if lang not in ("en", "zh"):
            return {"error": f"不支持的语言: {lang}"}

        dimensions = ASSESSMENT_DIMENSIONS[lang]
        assessment_id = str(uuid.uuid4())
        total_planned = self.default_questions_per_dimension * len(dimensions)

        # 初始等级估计（从中间等级开始）
        initial_level = "B1" if lang == "en" else "HSK3"

        self.logger.info(f"开始{lang}语言评估: user={user_id}, assessment={assessment_id}")

        # 持久化：创建 Assessment 记录
        if db and user_id:
            try:
                user_uuid = uuid.UUID(user_id)
                record = Assessment(
                    id=uuid.UUID(assessment_id),
                    user_id=user_uuid,
                    lang=lang,
                    status="in_progress",
                    total_questions=total_planned,
                )
                db.add(record)
                await db.commit()
                self.logger.info(f"Assessment 记录已创建: {assessment_id}")
            except (ValueError, Exception) as e:
                self.logger.warning(f"创建 Assessment 记录失败 (非致命): {e}")
                await db.rollback()

        return {
            "assessment_id": assessment_id,
            "lang": lang,
            "dimensions": dimensions,
            "current_level_estimate": initial_level,
            "next_dimension": dimensions[0],
            "total_questions_planned": total_planned,
            "level_system": "CEFR" if lang == "en" else "HSK",
            "level_range": list(CEFRLevel) if lang == "en" else list(HSKLevel),
        }

    # ── 2. 生成题目 ──
    async def generate_question(self, payload: dict) -> dict:
        """
        LLM生成一道自适应测试题

        payload:
        {
            "assessment_id": "...",
            "lang": "en",
            "dimension": "grammar",
            "current_level_estimate": "B1",
            "previous_results": [...]  # 可选，历史答题情况
        }

        返回：
        {
            "question_id": "uuid",
            "dimension": "grammar",
            "question_type": "multiple_choice",
            "question_text": "...",
            "options": [...],
            "difficulty": "medium",
            "level": "B1"
        }
        """
        lang = payload["lang"]
        dimension = payload["dimension"]
        level = payload.get("current_level_estimate", "B1" if lang == "en" else "HSK3")

        # 根据历史结果自适应调整难度
        previous = payload.get("previous_results", [])
        if previous:
            level = self._adapt_difficulty(level, previous, lang)

        # 构建 Prompt
        system = get_system_prompt(lang)
        question_prompt = get_test_prompt(dimension, lang)

        if not question_prompt:
            return {"error": f"未知评估维度: {dimension}"}

        # 生成题目参数（安全模板填充，避免 JSON {} 冲突）
        topics = self._get_topics_for_dimension(dimension, lang, level)
        user_prompt = self._fill_template(
            question_prompt,
            count=1,
            level=level,
            topics=topics,
            word_count=self._get_word_count(level, lang),
            topic=self._get_random_topic(dimension, lang),
            task_type=self._get_random_task_type(dimension),
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = await llm_service.chat_json(
                messages=messages,
                task="assessment",
            )

            # 阅读题特殊处理：LLM 返回 {passage, questions[]}
            if dimension == "reading" and "passage" in result:
                passage = result["passage"]
                raw_questions = result.get("questions", [])
                if isinstance(raw_questions, list) and raw_questions:
                    question = raw_questions[0]
                    question["passage"] = passage
                    question["question_type"] = question.get("type", "multiple_choice")
                else:
                    question = result
                    question["passage"] = passage
            else:
                questions = result.get("questions", [result])
                question = questions[0] if isinstance(questions, list) and questions else result

            question_id = str(uuid.uuid4())
            question["question_id"] = question_id
            question["dimension"] = dimension
            question["lang"] = lang

            # 兼容：如果 LLM 用 task_instruction 代替 question_text
            if "task_instruction" in question and "question_text" not in question:
                question["question_text"] = question["task_instruction"]

            self.logger.info(f"生成题目: dimension={dimension}, level={level}, type={question.get('type', 'unknown')}, has_passage={'passage' in question}")

            return {"question": question}

        except Exception as e:
            self.logger.error(f"生成题目失败: {e}")
            # 降级：返回预设题目
            return {"question": self._get_fallback_question(dimension, level, lang)}

    # ── 3. 提交答案并评分 ──
    async def submit_answer(self, payload: dict) -> dict:
        """
        提交答案，LLM评分并返回反馈

        payload:
        {
            "assessment_id": "...",
            "question_id": "...",
            "dimension": "grammar",
            "question_text": "...",
            "question_type": "multiple_choice|open_ended|writing",
            "correct_answer": "B",  # 如有
            "user_answer": "...",
            "lang": "en",
            "current_level_estimate": "B1",
        }
        """
        lang = payload["lang"]
        question_type = payload.get("question_type", "multiple_choice")
        user_answer = payload.get("user_answer", "")
        correct_answer = payload.get("correct_answer")

        result = {
            "question_id": payload.get("question_id"),
            "dimension": payload.get("dimension"),
            "is_correct": None,
            "score": None,
            "max_score": 10,
            "cefr_level": None,     # 这个回答体现的水平
            "feedback": None,
        }

        # 中文汉字类题型归一化
        ZH_CHAR_TYPES = {"write_character", "choose_character", "identify_radical"}
        effective_type = question_type
        if question_type in ZH_CHAR_TYPES:
            # write_character/choose_character → fill_blank 逻辑
            # identify_radical → 如果有correct_answer也走客观判分
            effective_type = "fill_blank"

        # 客观题（选择题/填空题）直接判分
        if effective_type in ("multiple_choice", "fill_blank") and correct_answer:
            result["is_correct"] = user_answer.strip().upper() == correct_answer.strip().upper()
            result["score"] = 10 if result["is_correct"] else 0
            result["feedback"] = "✅ 正确！" if result["is_correct"] else f"❌ 正确答案是 {correct_answer}"
            await self._save_question(payload, result, db=payload.get("db"))
            return result

        # 主观题（写作/开放题）LLM评分
        if question_type in ("open_ended", "writing", "speaking"):
            try:
                scoring_prompt = get_scoring_prompt(lang)
                prompt = self._fill_template(
                    scoring_prompt,
                    level=payload.get("current_level_estimate", "B1"),
                    task_description=payload.get("question_text", ""),
                    user_response=user_answer,
                )

                messages = [
                    {"role": "system", "content": get_system_prompt(lang)},
                    {"role": "user", "content": prompt},
                ]

                llm_result = await llm_service.chat_json(
                    messages=messages,
                    task="assessment",
                )

                # 提取评分
                scores = llm_result.get("scores", {})
                result["dimension_scores"] = scores

                # 计算综合分
                if scores:
                    all_scores = [s.get("score", 0) for s in scores.values() if isinstance(s, dict)]
                    result["score"] = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
                    result["max_score"] = 10

                result["feedback"] = llm_result.get("feedback", "")
                result["cefr_level"] = llm_result.get("overall_cefr") or llm_result.get("overall_hsk")

                self.logger.info(f"主观题评分: score={result['score']}, level={result['cefr_level']}")

            except Exception as e:
                self.logger.error(f"LLM评分失败: {e}")
                result["score"] = 5  # 降级默认
                result["feedback"] = "评分系统暂时不可用，已记录你的回答。"

        await self._save_question(payload, result, db=payload.get("db"))
        return result

    # ── 4. 生成评估报告 ──
    async def generate_report(self, payload: dict) -> dict:
        """
        汇总所有题目结果，生成综合评估报告

        payload:
        {
            "assessment_id": "...",
            "lang": "en",
            "all_answers": [
                {"dimension": "grammar", "score": 8, ...},
                ...
            ]
        }

        返回：
        {
            "overall_level": "B1",
            "dimension_scores": { ... },
            "summary": "...",
            "strengths": [...],
            "weaknesses": [...],
            "recommendations": [...],
            "next_level_estimate": { ... }
        }
        """
        lang = payload["lang"]
        all_answers = payload.get("all_answers", [])

        if len(all_answers) < self.min_questions_for_report:
            return {"error": f"题目数量不足（需要至少{self.min_questions_for_report}题）"}

        # 1. 本地统计：按维度汇总
        dimension_scores = self._aggregate_dimension_scores(all_answers, lang)

        # 2. 计算整体等级
        overall_level = self._compute_overall_level(dimension_scores, lang)

        # 3. LLM生成报告
        try:
            report_prompt = get_report_prompt(lang)
            prompt = self._fill_template(
                report_prompt,
                level=overall_level,
                questions_count=len(all_answers),
                dimensions=", ".join(dimension_scores.keys()),
                all_dimensions=", ".join(dimension_scores.keys()),
                dimension_scores=self._format_scores_for_prompt(dimension_scores),
            )

            messages = [
                {"role": "system", "content": get_system_prompt(lang)},
                {"role": "user", "content": prompt},
            ]

            llm_result = await llm_service.chat_json(
                messages=messages,
                task="assessment",
            )

            report = {
                "overall_level": overall_level,
                "level_system": "CEFR" if lang == "en" else "HSK",
                "dimension_scores": dimension_scores,
                "summary": llm_result.get("summary", ""),
                "strengths": llm_result.get("strengths", []),
                "weaknesses": llm_result.get("weaknesses", []),
                "recommendations": llm_result.get("recommendations", []),
                "next_level_estimate": llm_result.get("next_level_estimate", {}),
                "questions_answered": len(all_answers),
            }

        except Exception as e:
            self.logger.error(f"生成报告失败: {e}")
            # 降级：仅返回统计结果
            report = {
                "overall_level": overall_level,
                "level_system": "CEFR" if lang == "en" else "HSK",
                "dimension_scores": dimension_scores,
                "summary": f"你的{lang}语言水平评估为 {overall_level}",
                "strengths": [],
                "weaknesses": [],
                "recommendations": ["建议继续完成更多题目以获得详细分析"],
                "questions_answered": len(all_answers),
            }

        self.logger.info(f"生成报告: level={overall_level}, dimensions={list(dimension_scores.keys())}")

        # 持久化：更新 Assessment 记录为完成状态
        await self._finalize_assessment(payload, report)

        return report

    # ── 持久化辅助方法 ──
    async def _save_question(self, payload: dict, result: dict, db: Optional[AsyncSession]):
        """保存单道题的作答记录"""
        if not db:
            return
        try:
            assessment_id = payload.get("assessment_id")
            question_id = payload.get("question_id")
            if not assessment_id or not question_id:
                return

            # 计算 order_index（当前已回答数+1）
            from sqlalchemy import select, func
            count_result = await db.execute(
                select(func.count()).select_from(AssessmentQuestion)
                .where(AssessmentQuestion.assessment_id == uuid.UUID(assessment_id))
            )
            current_count = count_result.scalar() or 0

            q = AssessmentQuestion(
                id=uuid.UUID(question_id) if question_id else uuid.uuid4(),
                assessment_id=uuid.UUID(assessment_id),
                dimension=payload.get("dimension", "unknown"),
                difficulty=payload.get("current_level_estimate", "B1"),
                question_type=payload.get("question_type", "multiple_choice"),
                question_text=payload.get("question_text", ""),
                correct_answer=payload.get("correct_answer"),
                user_answer=payload.get("user_answer", ""),
                is_correct=result.get("is_correct"),
                score=result.get("score"),
                max_score=result.get("max_score", 10),
                llm_feedback=result.get("feedback"),
                order_index=current_count + 1,
            )
            db.add(q)

            # 更新 Assessment.answered_questions 计数
            from sqlalchemy import update
            await db.execute(
                update(Assessment)
                .where(Assessment.id == uuid.UUID(assessment_id))
                .values(answered_questions=current_count + 1)
            )

            await db.commit()
            self.logger.info(f"Question 记录已保存: {question_id}, order={current_count + 1}")
        except Exception as e:
            self.logger.warning(f"保存 Question 记录失败 (非致命): {e}")
            await db.rollback()

    async def _finalize_assessment(self, payload: dict, report: dict):
        """完成评估，更新 Assessment 记录"""
        db: Optional[AsyncSession] = payload.get("db")
        if not db:
            return
        try:
            assessment_id = payload.get("assessment_id")
            if not assessment_id:
                return

            from sqlalchemy import update
            await db.execute(
                update(Assessment)
                .where(Assessment.id == uuid.UUID(assessment_id))
                .values(
                    status="completed",
                    overall_level=report.get("overall_level"),
                    dimension_scores=report.get("dimension_scores", {}),
                    summary=report.get("summary", ""),
                    strengths=report.get("strengths", []),
                    weaknesses=report.get("weaknesses", []),
                    recommendations=report.get("recommendations", []),
                    answered_questions=report.get("questions_answered", 0),
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            self.logger.info(f"Assessment 已完成: {assessment_id}, level={report.get('overall_level')}")
        except Exception as e:
            self.logger.warning(f"更新 Assessment 失败 (非致命): {e}")
            await db.rollback()

    # ── 辅助方法 ──
    def _adapt_difficulty(self, current_level: str, previous_results: list, lang: str) -> str:
        """自适应调整题目难度"""
        if not previous_results:
            return current_level

        # 统计最近3题正确率
        recent = previous_results[-3:]
        correct_count = sum(1 for r in recent if r.get("is_correct") or (r.get("score", 0) >= settings.assess_correctness_threshold))
        total = len(recent)

        levels = list(CEFRLevel) if lang == "en" else list(HSKLevel)
        current_idx = levels.index(current_level) if current_level in levels else len(levels) // 2

        if correct_count == total:
            # 全对 → 提高难度
            new_idx = min(current_idx + 1, len(levels) - 1)
        elif correct_count <= total // 2:
            # 错了一半以上 → 降低难度
            new_idx = max(current_idx - 1, 0)
        else:
            new_idx = current_idx

        return levels[new_idx]

    def _aggregate_dimension_scores(self, answers: list, lang: str) -> dict:
        """按维度汇总分数"""
        dims = {}
        for a in answers:
            dim = a.get("dimension", "unknown")
            if dim not in dims:
                dims[dim] = {"scores": [], "level_estimates": []}

            score = a.get("score")
            if score is not None:
                dims[dim]["scores"].append(score)

            cefr = a.get("cefr_level")
            if cefr:
                dims[dim]["level_estimates"].append(cefr)

        result = {}
        for dim, data in dims.items():
            avg_score = round(sum(data["scores"]) / len(data["scores"]), 1) if data["scores"] else 0
            level = self._most_common(data["level_estimates"]) if data["level_estimates"] else "N/A"
            result[dim] = {
                "label": DIMENSION_LABELS.get(dim, dim),
                "average_score": avg_score,
                "max_score": 10,
                "estimated_level": level,
                "questions_count": len(data["scores"]),
            }

        return result

    def _compute_overall_level(self, dimension_scores: dict, lang: str) -> str:
        """计算整体等级"""
        if not dimension_scores:
            return "B1" if lang == "en" else "HSK3"

        # 计算加权平均分
        level_weights = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6,
                         "HSK1": 1, "HSK2": 2, "HSK3": 3, "HSK4": 4, "HSK5": 5, "HSK6": 6}

        total_weight = 0
        count = 0
        for dim, data in dimension_scores.items():
            lvl = data.get("estimated_level", "")
            if lvl in level_weights:
                total_weight += level_weights[lvl]
                count += 1

        if count == 0:
            return "B1" if lang == "en" else "HSK3"

        avg_weight = round(total_weight / count)

        # 映射回等级
        reverse_map = {v: k for k, v in level_weights.items()}
        # 找到最接近的等级
        levels = list(CEFRLevel) if lang == "en" else list(HSKLevel)
        candidate = reverse_map.get(avg_weight)
        if candidate and candidate in levels:
            return candidate
        return levels[min(avg_weight - 1, len(levels) - 1)]

    def _format_scores_for_prompt(self, dimension_scores: dict) -> str:
        """将维度分数格式化为 Prompt 文本"""
        lines = []
        for dim, data in dimension_scores.items():
            lines.append(f"- {data['label']}: {data['average_score']}/10 (≈{data['estimated_level']})")
        return "\n".join(lines)

    def _get_topics_for_dimension(self, dimension: str, lang: str, level: str) -> str:
        """获取对应维度的出题范围"""
        topics = {
            "en": {
                "grammar": "tenses, articles, prepositions, conditionals, passive voice, reported speech",
                "vocabulary": "daily life, business, academic, travel, technology, emotions, health, food",
                "reading": "daily life, work, travel, technology, culture, environment",
                "writing": "emails, essays, reports, stories, opinions, descriptions",
                "speaking": "introductions, daily routine, opinions, problem-solving, storytelling, debates",
            },
            "zh": {
                "characters": "常用汉字, 形近字辨析, 同音字, 多音字, 部首",
                "vocabulary": "日常生活, 商务, 学术, 旅行, 科技, 情感, 健康, 饮食",
                "grammar": "语序, 虚词(了/着/过/的/地/得), 把字句, 被字句, 补语, 复句",
                "reading": "日常生活, 社会话题, 科技, 文化, 环境",
                "writing": "信件, 短文, 报告, 叙事, 议论, 说明",
                "speaking": "自我介绍, 日常对话, 观点表达, 问题解决, 故事讲述, 辩论",
            },
        }
        return topics.get(lang, {}).get(dimension, "")

    def _get_word_count(self, level: str, lang: str) -> int:
        """根据等级返回建议字数"""
        if lang == "en":
            return {"A1": 80, "A2": 120, "B1": 180, "B2": 250, "C1": 350, "C2": 500}.get(level, 200)
        return {"HSK1": 50, "HSK2": 80, "HSK3": 120, "HSK4": 200, "HSK5": 300, "HSK6": 500}.get(level, 150)

    def _get_random_topic(self, dimension: str, lang: str) -> str:
        """返回随机话题"""
        topics_en = ["daily routine", "travel experience", "favorite food", "technology impact",
                     "environmental protection", "education system", "work-life balance", "cultural differences"]
        topics_zh = ["日常生活", "旅行经历", "美食文化", "科技发展", "环境保护", "教育话题", "职场生活", "传统文化"]
        topics = topics_en if lang == "en" else topics_zh
        import random
        return random.choice(topics)

    def _get_random_task_type(self, dimension: str) -> str:
        """返回随机任务类型"""
        import random
        task_types = {
            "writing": ["email", "essay", "report", "story"],
            "vocabulary": ["multiple_choice", "fill_blank", "matching"],
            "speaking": ["monologue", "dialogue", "presentation", "roleplay"],
        }
        return random.choice(task_types.get(dimension, ["multiple_choice"]))

    def _get_fallback_question(self, dimension: str, level: str, lang: str) -> dict:
        """LLM不可用时的降级题目"""
        qid = str(uuid.uuid4())
        if lang == "en" and dimension == "grammar":
            return {
                "question_id": qid,
                "dimension": "grammar",
                "type": "multiple_choice",
                "question_text": "She ___ to the store every Saturday.",
                "options": ["A) go", "B) goes", "C) going", "D) gone"],
                "correct_answer": "B",
                "difficulty": "easy",
                "cefr_level": level,
                "explanation": "第三人称单数需要用 goes",
                "grammar_rule": "Subject-Verb Agreement",
            }
        elif lang == "zh" and dimension == "grammar":
            return {
                "question_id": qid,
                "dimension": "grammar",
                "type": "multiple_choice",
                "question_text": "我___图书馆看书。",
                "options": ["A) 在", "B) 去", "C) 到", "D) 从"],
                "correct_answer": "A",
                "difficulty": "easy",
                "hsk_level": level,
                "explanation": "'在'表示在某处做某事",
                "grammar_rule": "介词'在'表示处所",
            }
        return {
            "question_id": qid,
            "dimension": dimension,
            "type": "open_ended",
            "question_text": f"请用{'英文' if lang == 'en' else '中文'}写一段关于日常生活的短文（50-100字）。",
            "difficulty": "medium",
            "cefr_level" if lang == "en" else "hsk_level": level,
        }

    @staticmethod
    def _most_common(items: list) -> str:
        """返回列表中出现最多的元素"""
        if not items:
            return ""
        return max(set(items), key=items.count)

    @staticmethod
    def _fill_template(template: str, **kwargs) -> str:
        """安全模板填充——用 {{key}} 替换，避免JSON花括号冲突"""
        result = template
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result
