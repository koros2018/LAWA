"""
LAWA 纠错服务

实时纠错引擎：
- 语法纠错（grammar）
- 词汇纠错（vocabulary）
- 表达优化（expression）
- 文化提示（cultural）

支持中/英双语纠错，LLM驱动。
"""
import json
from typing import Optional
from loguru import logger
from src.services.llm_service import llm_service


# ── Prompt 模板 ──

CORRECTION_SYSTEM_EN = """You are an expert English language tutor. Your job is to analyze a learner's message and provide corrections.

Rules:
1. Only flag REAL errors — don't over-correct
2. For each error, provide: original text, corrected text, error type, clear explanation
3. Error types: grammar, vocabulary, expression, spelling, cultural
4. Keep corrections concise and encouraging
5. If the message is perfect, say so — don't invent errors
6. For CEFR A1-A2 learners, be extra gentle
7. Include a "cultural_tip" field if culturally relevant

Return JSON format:
{
  "has_errors": true/false,
  "overall_comment": "brief overall feedback",
  "corrections": [
    {
      "original": "I goes to school",
      "corrected": "I go to school", 
      "type": "grammar",
      "explanation": "Third-person singular 'goes' is only for he/she/it. Use 'go' with 'I'.",
      "severity": "minor"
    }
  ],
  "cultural_tip": null or "string tip"
}"""

CORRECTION_SYSTEM_ZH = """你是一位专业的对外汉语教师。你的任务是分析汉语学习者的表达，提供纠错。

规则：
1. 只标记真正的错误——不要过度纠正
2. 每个错误提供：原文、改正后、错误类型、清晰解释
3. 错误类型：语法、词汇、表达、汉字、语用
4. 纠错要简洁、鼓励性
5. 如果表达完全正确，就说完全正确——不要编造错误
6. 对HSK1-2的初学者要格外温和
7. 如果有文化层面的提示，加入"cultural_tip"

返回JSON格式：
{
  "has_errors": true/false,
  "overall_comment": "总体简单评价",
  "corrections": [
    {
      "original": "我昨天去了学校昨天",
      "corrected": "我昨天去了学校",
      "type": "语法",
      "explanation": "时间状语重复。'昨天'出现一次就够了，中文时间状语通常放在主语后、动词前。",
      "severity": "minor"
    }
  ],
  "cultural_tip": null 或 "文化提示文字"
}"""


class CorrectionEngine:
    """实时纠错引擎"""

    def __init__(self):
        self.logger = logger.bind(engine="correction")

    async def correct(
        self,
        user_message: str,
        lang: str,
        user_level: str = "B1",
        context_messages: Optional[list] = None,
    ) -> dict:
        """
        分析用户消息并返回纠错

        Args:
            user_message: 用户发送的消息
            lang: 语言 (en/zh)
            user_level: 用户水平 (A1/A2/B1/B2/C1/C2 或 HSK1-6)
            context_messages: 最近的对话上下文

        Returns:
            {"has_errors": bool, "corrections": [...], "overall_comment": "...", "cultural_tip": "..."}
        """
        system = CORRECTION_SYSTEM_EN if lang == "en" else CORRECTION_SYSTEM_ZH

        # 构建上下文提示
        context_str = ""
        if context_messages:
            recent = context_messages[-4:]  # 最近4条
            lines = [f"{'User' if m['role'] == 'user' else 'Tutor'}: {m['content'][:200]}" for m in recent]
            context_str = "Recent conversation:\n" + "\n".join(lines) + "\n\n"

        user_prompt = f"""{context_str}Analyze this message from a {user_level} level {'English' if lang == 'en' else 'Chinese'} learner:

"{user_message}"

Return JSON with corrections (if any)."""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = await llm_service.chat_json(
                messages=messages,
                task="correction",
            )

            if "error" in result:
                self.logger.warning(f"纠错JSON解析失败: {result['error']}")
                return self._no_errors_result()

            self.logger.info(f"纠错: errors={result.get('has_errors')}, count={len(result.get('corrections', []))}")
            return result

        except Exception as e:
            self.logger.error(f"纠错LLM调用失败: {e}")
            return self._no_errors_result()

    async def correct_with_explanation(
        self,
        user_message: str,
        corrections: list,
        lang: str,
        user_level: str = "B1",
    ) -> str:
        """
        为纠错结果生成更详细的解释（用于用户追问"为什么"）
        """
        if not corrections:
            return "你的表达没有明显错误，很好！"

        system = CORRECTION_SYSTEM_EN if lang == "en" else CORRECTION_SYSTEM_ZH
        errors_text = json.dumps(corrections, ensure_ascii=False, indent=2)

        user_prompt = f"""The learner ({user_level} level) wrote: "{user_message}"

The following corrections were flagged:
{errors_text}

Please provide a friendly, detailed explanation of each error in {'English' if lang == 'en' else 'Chinese'}. Include tips for avoiding these mistakes in the future."""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

        try:
            return await llm_service.chat(
                messages=messages,
                task="correction",
                temperature=0.5,
                max_tokens=1000,
            )
        except Exception as e:
            self.logger.error(f"纠错解释生成失败: {e}")
            return "抱歉，详细解释暂时不可用。"

    def _no_errors_result(self) -> dict:
        return {
            "has_errors": False,
            "overall_comment": "表达清晰，没有发现明显错误。",
            "corrections": [],
            "cultural_tip": None,
        }


# 全局单例
correction_engine = CorrectionEngine()
