"""
LAWA 词汇服务

- 生词自动提取（从LLM回复中提取学习者可能不会的词）
- 间隔复习调度（基于 SM-2 算法的简化版）
- 复习队列生成
- DB持久化（CompanionVocabulary）
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.llm_service import llm_service


# ── Prompt 模板 ──

VOCAB_EXTRACTION_EN = """You are an English vocabulary extraction assistant.
Given a tutor's reply in a language learning conversation, identify words/phrases that a learner at the specified level might not know.

Rules:
1. Extract 0-5 words/phrases that are above the learner's current level
2. For each word: provide the word, a simple definition in English, part of speech, and the sentence from the reply where it appeared
3. Don't extract words the learner likely already knows at their level
4. Include idiomatic expressions and phrasal verbs
5. Return valid JSON only

Return format:
{
  "level_appropriate": true,
  "vocabulary": [
    {
      "word": "ubiquitous",
      "definition": "existing everywhere; very common",
      "part_of_speech": "adjective",
      "context_sentence": "Smartphones have become ubiquitous in modern life."
    }
  ]
}"""

VOCAB_EXTRACTION_ZH = """你是一个汉语词汇提取助手。
给定一段汉语教师在学习对话中的回复，识别出指定水平的学习者可能不认识的词汇。

规则：
1. 提取0-5个超出学习者当前水平的词汇/短语
2. 每个词汇提供：词、中文释义、词性、在回复中出现的原句
3. 不要提取学习者现有水平已经掌握的词汇
4. 包括成语、俗语和惯用表达
5. 只返回合法的JSON

返回格式：
{
  "level_appropriate": true,
  "vocabulary": [
    {
      "word": "未雨绸缪",
      "definition": "比喻事先做好准备",
      "part_of_speech": "成语",
      "context_sentence": "我们应该未雨绸缪，提前做好规划。"
    }
  ]
}"""


# ── SM-2 简化版间隔复习算法 ──

class SpacedRepetition:
    """SM-2 简化版间隔复习调度"""

    QUALITY_MULTIPLIERS = {
        0: 0.0,    # 完全忘记 → 重置
        1: 0.3,    # 错误但依稀记得
        2: 0.6,    # 错误但接近正确
        3: 1.0,    # 正确但有困难
        4: 1.5,    # 正确且轻松
        5: 2.0,    # 完美，毫不费力
    }

    INITIAL_INTERVAL = 4     # 4小时后第一次复习
    MIN_INTERVAL = 1         # 最小1小时
    MAX_INTERVAL = 8760      # 最大365天

    @classmethod
    def schedule_next_review(
        cls,
        current_interval: float,
        ease_factor: float,
        quality: int,
        review_count: int,
    ) -> tuple[float, float, int, bool]:
        if quality < 3:
            next_interval = cls.INITIAL_INTERVAL
            new_ease = max(1.3, ease_factor - 0.2)
            new_count = 0
            mastered = False
        else:
            if review_count == 0:
                next_interval = cls.INITIAL_INTERVAL
            elif review_count == 1:
                next_interval = 24
            else:
                multiplier = cls.QUALITY_MULTIPLIERS.get(quality, 1.0)
                next_interval = current_interval * ease_factor * multiplier

            new_ease = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            new_ease = max(1.3, min(2.5, new_ease))
            new_count = review_count + 1

        next_interval = max(cls.MIN_INTERVAL, min(cls.MAX_INTERVAL, next_interval))
        mastered = new_count >= 5 and quality >= 4

        return next_interval, new_ease, new_count, mastered

    @classmethod
    def next_review_at(cls, interval_hours: float) -> datetime:
        return datetime.now(timezone.utc) + timedelta(hours=interval_hours)


class VocabularyService:
    """词汇服务（DB持久化）"""

    def __init__(self):
        self.logger = logger.bind(service="vocabulary")

    # ── LLM 生词提取 ──

    async def extract_vocabulary(
        self,
        tutor_reply: str,
        lang: str,
        user_level: str = "B1",
    ) -> list[dict]:
        if len(tutor_reply) < 30:
            return []

        system = VOCAB_EXTRACTION_EN if lang == "en" else VOCAB_EXTRACTION_ZH
        level_label = user_level.replace("HSK", "HSK ") if "HSK" in user_level else user_level

        user_prompt = f"""Learner level: {level_label}
Tutor's reply:
---
{tutor_reply}
---
Extract vocabulary words this {level_label} learner might not know."""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = await llm_service.chat_json(messages=messages, task="simple")
            if "error" in result:
                self.logger.warning(f"生词提取失败: {result['error']}")
                return []
            vocab = result.get("vocabulary", [])
            self.logger.info(f"生词提取: {len(vocab)} 个")
            return vocab
        except Exception as e:
            self.logger.error(f"生词提取异常: {e}")
            return []

    # ── DB 持久化操作 ──

    async def save_vocabulary(
        self,
        db: AsyncSession,
        user_id: str,
        lang: str,
        words: list[dict],
        session_id: Optional[str] = None,
    ) -> list[dict]:
        """保存提取的生词到DB（去重）"""
        from src.models.companion import CompanionVocabulary

        saved = []
        for w in words:
            word_text = w.get("word", "").strip()
            if not word_text:
                continue

            # 去重检查
            exist = await db.execute(
                select(CompanionVocabulary).where(
                    CompanionVocabulary.user_id == user_id,
                    CompanionVocabulary.word == word_text,
                    CompanionVocabulary.lang == lang,
                )
            )
            if exist.scalar_one_or_none():
                continue

            entry = CompanionVocabulary(
                id=uuid.uuid4(),
                user_id=user_id,
                lang=lang,
                word=word_text,
                definition=w.get("definition", ""),
                part_of_speech=w.get("part_of_speech", ""),
                example_sentence=w.get("context_sentence", w.get("example_sentence", "")),
                source_session_id=session_id,
                review_count=0,
                review_interval_hours=0,
                ease_factor=2.5,
                next_review_at=SpacedRepetition.next_review_at(SpacedRepetition.INITIAL_INTERVAL),
            )
            db.add(entry)
            saved.append(entry)

        if saved:
            await db.commit()
            self.logger.info(f"保存生词: {len(saved)} 个 (user={user_id})")

        return [{"word": e.word, "definition": e.definition} for e in saved]

    async def get_review_queue(
        self,
        db: AsyncSession,
        user_id: str,
        lang: str,
        limit: int = 20,
    ) -> list[dict]:
        """获取待复习的词汇队列"""
        from src.models.companion import CompanionVocabulary

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(CompanionVocabulary).where(
                CompanionVocabulary.user_id == user_id,
                CompanionVocabulary.lang == lang,
                CompanionVocabulary.is_mastered == False,
                CompanionVocabulary.next_review_at <= now,
            ).order_by(CompanionVocabulary.next_review_at.asc()).limit(limit)
        )
        items = result.scalars().all()

        queue = []
        for item in items:
            overdue_hours = (now - item.next_review_at).total_seconds() / 3600 if item.next_review_at else 0
            queue.append({
                "id": str(item.id),
                "word": item.word,
                "definition": item.definition,
                "part_of_speech": item.part_of_speech,
                "example_sentence": item.example_sentence,
                "review_count": item.review_count,
                "ease_factor": item.ease_factor,
                "is_mastered": item.is_mastered,
                "last_review_at": item.last_review_at.isoformat() if item.last_review_at else None,
                "next_review_at": item.next_review_at.isoformat() if item.next_review_at else None,
                "priority": round(overdue_hours * (1.0 / max(0.5, item.ease_factor)), 2),
            })
        queue.sort(key=lambda x: x["priority"], reverse=True)
        return queue

    async def review_vocabulary(
        self,
        db: AsyncSession,
        vocab_id: str,
        quality: int,
    ) -> dict:
        """记录一次复习结果，更新SM-2调度"""
        from src.models.companion import CompanionVocabulary

        result = await db.execute(
            select(CompanionVocabulary).where(CompanionVocabulary.id == vocab_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return {"error": "Vocabulary not found"}

        next_interval, new_ease, new_count, mastered = SpacedRepetition.schedule_next_review(
            current_interval=entry.review_interval_hours,
            ease_factor=entry.ease_factor,
            quality=quality,
            review_count=entry.review_count,
        )

        entry.review_count = new_count
        entry.review_interval_hours = next_interval
        entry.ease_factor = new_ease
        entry.last_review_at = datetime.now(timezone.utc)
        entry.next_review_at = SpacedRepetition.next_review_at(next_interval)
        entry.is_mastered = mastered

        await db.commit()
        self.logger.info(f"复习: {entry.word} | quality={quality} → interval={next_interval:.1f}h mastered={mastered}")

        return {
            "id": str(entry.id),
            "word": entry.word,
            "quality": quality,
            "next_interval_hours": round(next_interval, 1),
            "next_review_at": entry.next_review_at.isoformat(),
            "is_mastered": mastered,
        }

    async def get_vocabulary_list(
        self,
        db: AsyncSession,
        user_id: str,
        lang: str,
        mastered: Optional[bool] = None,
        limit: int = 100,
    ) -> dict:
        """获取用户词汇列表"""
        from src.models.companion import CompanionVocabulary

        query = select(CompanionVocabulary).where(
            CompanionVocabulary.user_id == user_id,
            CompanionVocabulary.lang == lang,
        )
        if mastered is not None:
            query = query.where(CompanionVocabulary.is_mastered == mastered)

        query = query.order_by(CompanionVocabulary.created_at.desc()).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()

        words = []
        for item in items:
            words.append({
                "id": str(item.id),
                "word": item.word,
                "definition": item.definition,
                "part_of_speech": item.part_of_speech,
                "example_sentence": item.example_sentence,
                "review_count": item.review_count,
                "ease_factor": round(item.ease_factor, 2),
                "is_mastered": item.is_mastered,
                "next_review_at": item.next_review_at.isoformat() if item.next_review_at else None,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            })

        return {"vocabulary": words, "total": len(words)}

    async def get_review_stats(
        self,
        db: AsyncSession,
        user_id: str,
        lang: str,
    ) -> dict:
        """获取词汇复习统计"""
        from src.models.companion import CompanionVocabulary
        from sqlalchemy import func

        # 总数
        total_result = await db.execute(
            select(func.count(CompanionVocabulary.id)).where(
                CompanionVocabulary.user_id == user_id,
                CompanionVocabulary.lang == lang,
            )
        )
        total = total_result.scalar() or 0

        # 已掌握
        m_result = await db.execute(
            select(func.count(CompanionVocabulary.id)).where(
                CompanionVocabulary.user_id == user_id,
                CompanionVocabulary.lang == lang,
                CompanionVocabulary.is_mastered == True,
            )
        )
        mastered = m_result.scalar() or 0

        # 今日待复习
        now = datetime.now(timezone.utc)
        d_result = await db.execute(
            select(func.count(CompanionVocabulary.id)).where(
                CompanionVocabulary.user_id == user_id,
                CompanionVocabulary.lang == lang,
                CompanionVocabulary.is_mastered == False,
                CompanionVocabulary.next_review_at <= now,
            )
        )
        due_today = d_result.scalar() or 0

        return {
            "total": total,
            "mastered": mastered,
            "learning": total - mastered,
            "due_today": due_today,
            "mastery_rate": round(mastered / total * 100, 1) if total > 0 else 0,
        }


# 全局单例
vocabulary_service = VocabularyService()
spaced_repetition = SpacedRepetition()
