"""
LAWA 评估数据模型

评估记录 + 测试题目 + 评分结果
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, JSON, func
from src.models.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.main import Base


class Assessment(Base):
    """评估记录"""
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    lang: Mapped[str] = mapped_column(String(5), nullable=False)  # zh | en
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress | completed

    # 等级结果
    overall_level: Mapped[str] = mapped_column(String(10), nullable=True)  # A1~C2 / HSK1~6
    dimension_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"grammar": {"level": "B1", "score": 72, "max": 100}, "reading": {...}, ...}

    # 评估元数据
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    answered_questions: Mapped[int] = mapped_column(Integer, default=0)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # LLM综合评语
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    strengths: Mapped[list] = mapped_column(JSON, default=list)     # ["语法准确", "词汇丰富"]
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)    # ["口语不流利", "写作结构弱"]
    recommendations: Mapped[list] = mapped_column(JSON, default=list)  # ["建议每天练习口语", "重点突破写作"]

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # 关联题目
    questions: Mapped[list["AssessmentQuestion"]] = relationship(back_populates="assessment")


class AssessmentQuestion(Base):
    """评估题目"""
    __tablename__ = "assessment_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False)

    # 题目信息
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)  # grammar | vocabulary | reading | writing | characters
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False)  # easy | medium | hard
    question_type: Mapped[str] = mapped_column(String(20), nullable=False)  # multiple_choice | fill_blank | open_ended | writing
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSON, nullable=True)       # 选择题选项
    correct_answer: Mapped[str] = mapped_column(Text, nullable=True) # 正确答案（客观题）

    # 用户回答
    user_answer: Mapped[str] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=True)       # 得分（主观题LLM评分）
    max_score: Mapped[int] = mapped_column(Integer, default=10)
    llm_feedback: Mapped[str] = mapped_column(Text, nullable=True)   # LLM评语

    # 元数据
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关联
    assessment: Mapped["Assessment"] = relationship(back_populates="questions")
