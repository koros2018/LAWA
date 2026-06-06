"""
LAWA CompanionAgent — AI伴读 Agent

核心功能：
- 场景化对话（10个中/英文场景）
- 实时纠错（语法+词汇+表达+文化提示）
- 生词自动提取（间隔复习）
- 对话管理（DB持久化 + 超时自动清理）
- 对话后总结 + 导师反馈更新
"""
import json
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from loguru import logger
from pathlib import Path

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.agent.base_agent import BaseAgent
from src.config import settings
from src.database import AsyncSessionLocal
from src.database.session import get_async_session
from src.services.llm_service import llm_service
from src.services.correction import correction_engine
from src.services.vocabulary import vocabulary_service, spaced_repetition
from src.models.companion import CompanionSession, CompanionMessage, CompanionVocabulary


# ── 加载场景库 ──
def _load_scenarios():
    data_dir = Path(__file__).parent.parent / "data"
    scenarios = {}
    try:
        with open(data_dir / "scenarios_en.json", "r") as f:
            scenarios["en"] = json.load(f)
        with open(data_dir / "scenarios_zh.json", "r") as f:
            scenarios["zh"] = json.load(f)
        logger.info(f"✅ 场景库加载: en={len(scenarios['en']['scenarios'])} zh={len(scenarios['zh']['scenarios'])}")
    except Exception as e:
        logger.warning(f"场景库加载失败: {e}，使用空场景集")
        scenarios = {"en": {"scenarios": []}, "zh": {"scenarios": []}}
    return scenarios


SCENARIOS = _load_scenarios()

# ── System Prompts ──

COMPANION_SYSTEM_EN = """You are an AI language companion helping a learner practice English through natural conversation.

Your role:
- You are role-playing as: {persona}
- Current scenario: {scenario_title}
- Setting: {context_setting}
- Learner's CEFR level: {level}

Guidelines:
1. Stay in character — you are {persona}
2. Match your language complexity to the learner's level ({level})
3. Keep responses natural and conversational (2-4 sentences usually)
4. Encourage the learner to speak more — ask follow-up questions
5. Gently introduce new vocabulary at {level}+1 level
6. If the learner struggles, offer hints or simplify your language
7. Be encouraging and positive
8. Occasionally pose choices or open-ended questions to keep the conversation flowing

Learning goals: {learning_goals}
Suggested phrases: {suggested_phrases}"""

COMPANION_SYSTEM_ZH = """你是一位AI语言伴读，帮助学习者通过自然对话练习中文。

你的角色：
- 你正在扮演：{persona}
- 当前场景：{scenario_title}
- 场景设置：{context_setting}
- 学习者的HSK水平：{level}

指导原则：
1. 保持角色——你是{persona}
2. 根据学习者的水平({level})调整语言难度
3. 回复保持自然、口语化（通常2-4句）
4. 鼓励学习者多说——用追问来延续对话
5. 温和地引入比{level}高一级的词汇
6. 如果学习者遇到困难，给予提示或简化语言
7. 保持鼓励和积极的态度
8. 偶尔给出选择或开放式问题，让对话更自然

学习目标：{learning_goals}
建议表达：{suggested_phrases}"""

# ── 超时配置 ──
SESSION_TIMEOUT_MINUTES = 30  # 会话无活动超过此时间自动标记为 abandoned


class CompanionAgent(BaseAgent):
    """AI伴读 Agent — 全 DB 持久化 + 超时自动清理"""

    def __init__(self):
        super().__init__("CompanionAgent")
        self.timeout_seconds = 120  # LLM 对话需要更长时间

    async def execute(self, payload: dict) -> dict:
        """
        执行伴读操作

        payload:
        {
            "action": "start_session | send_message | end_session | list_scenarios | get_session | list_sessions | cleanup_stale",
            "user_id": "...",
            "lang": "en" | "zh",
            "session_id": "...",
            "scenario_id": "...",
            "message": "...",
            "user_level": "B1",
        }
        """
        action = payload.get("action", "start_session")

        handlers = {
            "start_session": self.start_session,
            "send_message": self.send_message,
            "end_session": self.end_session,
            "list_scenarios": self.list_scenarios,
            "generate_scenario": self.generate_scenario,
            "get_session": self.get_session,
            "list_sessions": self.list_sessions,
            "cleanup_stale": self.cleanup_stale_sessions,
        }

        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}

        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    # ── 序列化辅助 ──
    @staticmethod
    def _session_to_dict(s: CompanionSession, include_messages: bool = False) -> dict:
        d = {
            "session_id": str(s.id),
            "user_id": str(s.user_id),
            "lang": s.lang,
            "scenario_id": s.scenario_id,
            "status": s.status,
            "message_count": s.message_count,
            "user_message_count": s.user_message_count,
            "total_corrections": s.total_corrections,
            "total_vocabulary": s.total_vocabulary,
            "duration_seconds": s.duration_seconds,
            "coins_earned": s.coins_earned,
            "summary": s.summary,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        }
        if include_messages and hasattr(s, 'messages'):
            d["messages"] = [
                {
                    "role": m.role,
                    "content": m.content,
                    "corrections": m.corrections,
                    "vocabulary_extracted": m.vocabulary_extracted,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in (s.messages or [])
            ]
        return d

    # ── 1. 列出场景 ──
    async def list_scenarios(self, payload: dict) -> dict:
        """获取指定语言的场景列表"""
        lang = payload.get("lang", "en")
        scenarios_data = SCENARIOS.get(lang, {"scenarios": []})

        scenario_list = []
        for s in scenarios_data["scenarios"]:
            scenario_list.append({
                "id": s["id"],
                "title": s["title"],
                "description": s["description"],
                "difficulty": s["difficulty"],
                "topic_tags": s["topic_tags"],
            })

        return {
            "lang": lang,
            "count": len(scenario_list),
            "scenarios": scenario_list,
        }

    # ── 2. 列出用户会话 ──
    async def list_sessions(self, payload: dict) -> dict:
        """列出用户的所有会话（从DB查询）"""
        user_id = payload.get("user_id")
        if not user_id:
            return {"error": "user_id required"}

        async with get_async_session() as db:
            result = await db.execute(
                select(CompanionSession)
                .where(CompanionSession.user_id == user_id)
                .order_by(CompanionSession.created_at.desc())
            )
            sessions = result.scalars().all()

        return {
            "sessions": [self._session_to_dict(s) for s in sessions],
            "count": len(sessions),
        }

    # ── 3. 获取会话详情 ──
    async def get_session(self, payload: dict) -> dict:
        """获取会话详情（含最近消息）"""
        session_id = payload.get("session_id")
        if not session_id:
            return {"error": "session_id required"}

        async with get_async_session() as db:
            result = await db.execute(
                select(CompanionSession).where(CompanionSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                return {"error": f"Session not found: {session_id}"}

            # 查询最近20条消息
            msg_result = await db.execute(
                select(CompanionMessage)
                .where(CompanionMessage.session_id == session_id)
                .order_by(CompanionMessage.created_at.desc())
                .limit(20)
            )
            session.messages = list(msg_result.scalars().all())[::-1]  # 反转回时间顺序

        return self._session_to_dict(session, include_messages=True)

    # ── 4. 启动会话 ──
    async def start_session(self, payload: dict) -> dict:
        """
        创建新的伴读会话（持久化到DB）
        """
        user_id = payload.get("user_id")
        lang = payload.get("lang", "en")
        scenario_id = payload.get("scenario_id")
        user_level = payload.get("user_level", "B1" if lang == "en" else "HSK3")

        if lang not in ("en", "zh"):
            return {"error": f"不支持的语言: {lang}"}

        # 找场景
        scenarios_data = SCENARIOS.get(lang, {"scenarios": []})
        scenario = None
        if scenario_id:
            for s in scenarios_data["scenarios"]:
                if s["id"] == scenario_id:
                    scenario = s
                    break

        if not scenario:
            import random
            candidates = [s for s in scenarios_data["scenarios"]]
            if candidates:
                scenario = random.choice(candidates)
            else:
                return {"error": "没有可用场景"}

        # 构建系统提示
        system_template = COMPANION_SYSTEM_EN if lang == "en" else COMPANION_SYSTEM_ZH
        system_prompt = system_template.format(
            persona=scenario["persona"],
            scenario_title=scenario["title"],
            context_setting=scenario["context_setting"],
            level=user_level,
            learning_goals=", ".join(scenario["learning_goals"]),
            suggested_phrases=", ".join(scenario["suggested_phrases"]),
        )

        # 生成开场白
        greeting_prompt = f"""You are starting a conversation as: {scenario['persona']}
Setting: {scenario['context_setting']}
Learner level: {user_level}

Give a warm, natural opening greeting (2-3 sentences) to start the conversation. Be in character."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": greeting_prompt},
        ]

        greeting = await llm_service.chat(
            messages=messages,
            task="companion",
            temperature=0.8,
            max_tokens=300,
        )

        # 提取场景相关词汇
        vocab_items = await vocabulary_service.extract_vocabulary(
            tutor_reply=greeting,
            lang=lang,
            user_level=user_level,
        )

        # ── 持久化到 DB ──
        session_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        async with get_async_session() as db:
            session = CompanionSession(
                id=session_id,
                user_id=user_id,
                lang=lang,
                scenario_id=scenario["id"],
                status="active",
                message_count=1,
                coins_earned=0,
                last_activity_at=now,
            )
            db.add(session)

            # 初始系统消息
            db.add(CompanionMessage(
                session_id=session_id,
                role="system",
                content=system_prompt,
                created_at=now,
            ))
            # AI 开场白
            db.add(CompanionMessage(
                session_id=session_id,
                role="assistant",
                content=greeting,
                vocabulary_extracted=vocab_items,
                created_at=now,
            ))

            await db.commit()

        logger.info(f"新建会话: {str(session_id)[:8]} | {scenario['title']} | level={user_level}")

        return {
            "session_id": str(session_id),
            "scenario": {
                "id": scenario["id"],
                "title": scenario["title"],
                "description": scenario["description"],
                "difficulty": scenario["difficulty"],
                "persona": scenario["persona"],
                "context_setting": scenario["context_setting"],
            },
            "greeting": greeting,
            "vocabulary": vocab_items,
            "suggested_phrases": scenario["suggested_phrases"],
            "learning_goals": scenario["learning_goals"],
            "tips": f"开始练习{scenario['title']}场景吧！记得语音输入更方便哦 🎙️",
        }

    # ── 5. 发送消息（核心对话）──
    async def send_message(self, payload: dict) -> dict:
        """
        用户发送消息，获取AI回复 + 纠错 + 生词（全部持久化到DB）
        """
        session_id = payload.get("session_id")
        user_message = payload.get("message", "").strip()

        if not session_id:
            return {"error": "session_id required"}
        if not user_message:
            return {"error": "消息不能为空"}

        async with get_async_session() as db:
            # 查询会话
            result = await db.execute(
                select(CompanionSession).where(CompanionSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                return {"error": f"会话不存在: {session_id}"}
            if session.status != "active":
                return {"error": f"会话已结束 (status={session.status})"}

            lang = session.lang

            # 获取场景信息用于构建上下文
            scenario = None
            scenarios_data = SCENARIOS.get(lang, {"scenarios": []})
            for s in scenarios_data["scenarios"]:
                if s["id"] == session.scenario_id:
                    scenario = s
                    break

            # 查询历史消息构建上下文
            msg_result = await db.execute(
                select(CompanionMessage)
                .where(CompanionMessage.session_id == session_id)
                .order_by(CompanionMessage.created_at.asc())
            )
            all_messages = list(msg_result.scalars().all())

            # 构建LLM上下文（保留 system prompt + 最近15轮）
            context_messages = []
            for m in all_messages:
                context_messages.append({"role": m.role, "content": m.content})

            MAX_CONTEXT = 15 * 2 + 1  # 15轮 + system
            if len(context_messages) > MAX_CONTEXT:
                context_messages = context_messages[:1] + context_messages[-(MAX_CONTEXT - 1):]

            # 获取 user_level（从场景或默认）
            user_level = "B1" if lang == "en" else "HSK3"

            # 1) 纠错（并行）
            correction_task = correction_engine.correct(
                user_message=user_message,
                lang=lang,
                user_level=user_level,
                context_messages=context_messages[-6:],
            )

            # 2) 生成AI回复
            context_messages.append({"role": "user", "content": user_message})

            assistant_reply = await llm_service.chat(
                messages=context_messages,
                task="companion",
                temperature=0.8,
                max_tokens=500,
            )

            # 3) 提取生词
            vocab_items = await vocabulary_service.extract_vocabulary(
                tutor_reply=assistant_reply,
                lang=lang,
                user_level=user_level,
            )

            # 4) 等待纠错完成
            correction_result = await correction_task

            # ── 持久化消息到 DB ──
            now = datetime.now(timezone.utc)
            db.add(CompanionMessage(
                session_id=session_id,
                role="user",
                content=user_message,
                corrections=correction_result.get("corrections", []),
                created_at=now,
            ))
            db.add(CompanionMessage(
                session_id=session_id,
                role="assistant",
                content=assistant_reply,
                vocabulary_extracted=vocab_items,
                created_at=now,
            ))

            # 更新会话统计
            session.message_count = (session.message_count or 0) + 2
            session.user_message_count = (session.user_message_count or 0) + 1
            session.total_corrections = (session.total_corrections or 0) + len(correction_result.get("corrections", []))
            session.total_vocabulary = (session.total_vocabulary or 0) + len(vocab_items)
            session.coins_earned = (session.coins_earned or 0) + 1
            session.last_activity_at = now
            session.updated_at = now

            await db.commit()

            logger.info(
                f"对话: session={str(session_id)[:8]} | "
                f"msg#{(session.message_count or 0)//2} | "
                f"corrections={len(correction_result.get('corrections',[]))} | "
                f"vocab={len(vocab_items)}"
            )

            return {
                "session_id": str(session_id),
                "user_message": user_message,
                "assistant_reply": assistant_reply,
                "corrections": correction_result.get("corrections", []),
                "has_errors": correction_result.get("has_errors", False),
                "overall_comment": correction_result.get("overall_comment", ""),
                "cultural_tip": correction_result.get("cultural_tip"),
                "vocabulary": vocab_items,
                "message_count": (session.message_count or 0) // 2,
                "coins_earned_session": session.coins_earned or 0,
            }

    # ── 6. 结束会话 ──
    async def end_session(self, payload: dict) -> dict:
        """
        结束伴读会话，生成总结 + 学习报告（持久化到DB）
        """
        session_id = payload.get("session_id")
        if not session_id:
            return {"error": "session_id required"}

        async with get_async_session() as db:
            result = await db.execute(
                select(CompanionSession).where(CompanionSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                return {"error": f"会话不存在: {session_id}"}
            if session.status != "active":
                return {"error": "会话已结束"}

            lang = session.lang

            # 查询所有消息
            msg_result = await db.execute(
                select(CompanionMessage)
                .where(CompanionMessage.session_id == session_id)
                .order_by(CompanionMessage.created_at.asc())
            )
            all_messages = list(msg_result.scalars().all())

            # 收集所有生词
            all_vocab = []
            for m in all_messages:
                if m.role == "assistant" and m.vocabulary_extracted:
                    all_vocab.extend(m.vocabulary_extracted)

            # 计算时长
            if session.created_at:
                duration_seconds = int((datetime.now(timezone.utc) - session.created_at).total_seconds())
            else:
                duration_seconds = 0

            # 获取场景信息
            scenario_title = "Unknown"
            scenarios_data = SCENARIOS.get(lang, {"scenarios": []})
            for s in scenarios_data["scenarios"]:
                if s["id"] == session.scenario_id:
                    scenario_title = s["title"]
                    break

            # 生成总结
            total_rounds = session.user_message_count or 0
            summary_prompt = f"""The language practice session has ended.

Language: {'English' if lang == 'en' else 'Chinese'}
Scenario: {scenario_title}
Messages exchanged: {total_rounds} rounds
Corrections made: {session.total_corrections or 0}
Vocabulary extracted: {len(all_vocab)}

Please provide a friendly summary including:
1. Overall performance assessment (2-3 sentences)
2. What the learner did well
3. Areas to improve
4. 2-3 specific recommendations for next practice

Return JSON:
{{
  "overall_assessment": "...",
  "strengths": ["...", "..."],
  "areas_to_improve": ["...", "..."],
  "recommendations": ["...", "...", "..."]
}}"""

            # 从消息中取 system prompt
            system_prompt = ""
            for m in all_messages:
                if m.role == "system":
                    system_prompt = m.content
                    break

            summary_messages = [
                {"role": "system", "content": system_prompt or "You are a language tutor."},
                {"role": "user", "content": summary_prompt},
            ]

            try:
                summary = await llm_service.chat_json(
                    messages=summary_messages,
                    task="simple",
                )
            except Exception as e:
                logger.error(f"总结生成失败: {e}")
                summary = {
                    "overall_assessment": f"完成了{total_rounds}轮{scenario_title}场景对话练习。",
                    "strengths": ["积极参与对话"],
                    "areas_to_improve": ["继续练习"],
                    "recommendations": ["每天练习15-20分钟", "复习本次学到的生词", "尝试更难一级的场景"],
                }

            # ── 更新会话到 DB ──
            now = datetime.now(timezone.utc)
            session.status = "completed"
            session.ended_at = now
            session.updated_at = now
            session.last_activity_at = now
            session.duration_seconds = duration_seconds
            session.summary = summary.get("overall_assessment", "")

            await db.commit()

            stats = {
                "message_rounds": total_rounds,
                "corrections_count": session.total_corrections or 0,
                "vocabulary_count": len(all_vocab),
                "coins_earned": session.coins_earned or 0,
                "scenario": scenario_title,
                "duration_minutes": round(duration_seconds / 60, 1),
            }

            logger.info(f"会话结束: {str(session_id)[:8]} | rounds={stats['message_rounds']} | coins={stats['coins_earned']}")

            return {
                "session_id": str(session_id),
                "summary": summary,
                "stats": stats,
                "vocabulary": all_vocab,
                "recommendations": summary.get("recommendations", []),
                "farewell": "Great practice today! Keep it up! 🎉" if lang == "en" else "今天练习很棒！再接再厉！🎉",
                "coins_earned": session.coins_earned or 0,
            }

    # ── 7. 清理过期会话 ──
    async def cleanup_stale_sessions(self, payload: dict = None) -> dict:
        """
        将超过 SESSION_TIMEOUT_MINUTES 无活动的 active 会话标记为 abandoned

        payload (可选):
        {
            "timeout_minutes": 30,  # 可选，默认 SESSION_TIMEOUT_MINUTES
            "dry_run": false,       # 可选，仅统计不执行
        """
        if payload is None:
            payload = {}
        timeout_minutes = payload.get("timeout_minutes", SESSION_TIMEOUT_MINUTES)
        dry_run = payload.get("dry_run", False)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

        async with get_async_session() as db:
            # 查询过期会话
            result = await db.execute(
                select(CompanionSession)
                .where(
                    CompanionSession.status == "active",
                    CompanionSession.last_activity_at < cutoff,
                )
            )
            stale_sessions = result.scalars().all()

            count = len(stale_sessions)
            session_ids = [str(s.id) for s in stale_sessions]

            if not dry_run and count > 0:
                now = datetime.now(timezone.utc)
                for s in stale_sessions:
                    s.status = "abandoned"
                    s.ended_at = now
                    s.updated_at = now
                await db.commit()
                logger.info(f"🧹 清理过期会话: {count} 个 (timeout={timeout_minutes}min)")

        return {
            "cleaned": 0 if dry_run else count,
            "stale_count": count,
            "timeout_minutes": timeout_minutes,
            "cutoff": cutoff.isoformat(),
            "session_ids": session_ids[:20],
            "dry_run": dry_run,
        }

    # ── 8. 动态场景生成（LLM）──
    async def generate_scenario(self, payload: dict) -> dict:
        """由 LLM 根据用户水平/兴趣实时生成个性化场景"""
        lang = payload.get("lang", "en")
        user_level = payload.get("user_level", "B1" if lang == "en" else "HSK3")
        interest = payload.get("interest", "daily_life")
        topic = payload.get("topic", "")

        if lang == "en":
            system_prompt = f"""You are a creative language teaching scenario designer.
Generate a realistic, engaging role-play scenario for an English learner at CEFR level {user_level}.

Interest area: {interest}
{f"Specific topic: {topic}" if topic else ""}

Return a JSON object with exactly these fields:
{{
  "id": "gen_<short_descriptive_slug>",
  "title": "Catchy scenario title with emoji",
  "description": "2-3 sentences setting up the situation",
  "difficulty": "{user_level}",
  "topic_tags": ["tag1", "tag2", "tag3"],
  "persona": "Detailed character description for the AI to role-play (name, personality, speaking style)",
  "context_setting": "Vivid description of the physical setting and atmosphere",
  "learning_goals": ["goal1", "goal2", "goal3"],
  "suggested_phrases": ["phrase1", "phrase2", "phrase3", "phrase4"]
}}

Make it practical, culturally authentic, and fun."""
        else:
            system_prompt = f"""你是一位创意语言教学场景设计师。
为HSK{user_level[-1] if user_level.startswith('HSK') else '3'}水平的中文学习者生成一个真实、有趣的角色扮演场景。

兴趣领域：{interest}
{f"具体主题：{topic}" if topic else ""}

返回一个JSON对象：
{{
  "id": "gen_<简短描述性英文slug>",
  "title": "吸引人的场景标题，带emoji",
  "description": "2-3句话描述情境",
  "difficulty": "{user_level}",
  "topic_tags": ["标签1", "标签2", "标签3"],
  "persona": "详细的AI角色描述（名字、性格、说话风格）",
  "context_setting": "生动的场景环境和氛围描述",
  "learning_goals": ["目标1", "目标2", "目标3"],
  "suggested_phrases": ["表达1", "表达2", "表达3", "表达4"]
}}

要实用、有文化真实性、有趣。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate a scenario for {interest} at level {user_level}."},
        ]

        scenario = await llm_service.chat_json(
            messages=messages,
            task="companion",
            temperature=0.9,
        )

        required_fields = ["id", "title", "description", "difficulty", "topic_tags",
                           "persona", "context_setting", "learning_goals", "suggested_phrases"]
        for field in required_fields:
            if field not in scenario:
                scenario[field] = f"__missing_{field}__"

        logger.info(f"🎭 动态场景生成: {scenario.get('title', '?')} | level={user_level} | interest={interest}")

        return {
            "scenario": scenario,
            "generated": True,
            "lang": lang,
            "level": user_level,
            "interest": interest,
        }
