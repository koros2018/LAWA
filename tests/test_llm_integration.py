"""
LAWA LLM 集成测试 — 使用 DeepSeek API

覆盖所有 LLM 依赖的 Agent 执行路径：
- companion_agent: 伴读对话
- assessment_agent: 评估出题/评分
- tutor_agent: 导师对话
- persona_agent: 画像推断
- plan_agent: 计划生成
- llm_service: 多Provider路由 + 熔断 + 重试

用法:
  cd Projects/LAWA && source .venv/bin/activate
  PYTHONPATH=. python -m pytest tests/test_llm_integration.py -v -s
  或单测: PYTHONPATH=. python tests/test_llm_integration.py
"""
import asyncio
import os
import pytest
from openai import AsyncOpenAI

# 确保 DeepSeek 可用
DEEPSEEK_KEY = os.environ.get("LLM_DEEPSEEK_KEY", "")
DEEPSEEK_BASE = os.environ.get("LLM_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.environ.get("LLM_DEEPSEEK_MODEL", "deepseek-chat")

requires_deepseek = pytest.mark.skipif(
    not DEEPSEEK_KEY,
    reason="LLM_DEEPSEEK_KEY not set"
)


# ══════════════════════════════════════════
# 1. LLM Service 基础功能
# ══════════════════════════════════════════

class TestLLMService:
    """LLM 服务核心功能"""

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_chat_simple(self):
        """简单对话"""
        from src.services.llm_service import llm_service
        r = await llm_service.chat(
            messages=[{"role": "user", "content": "Reply with exactly: HELLO_OK"}],
            provider="deepseek",
            max_tokens=20,
        )
        assert "HELLO_OK" in r.upper(), f"Expected HELLO_OK, got: {r[:50]}"

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_chat_json(self):
        """结构化 JSON 输出"""
        from src.services.llm_service import llm_service
        r = await llm_service.chat_json(
            messages=[{
                "role": "user",
                "content": 'Return JSON: {"status": "ok", "value": 42}'
            }],
            provider="deepseek",
        )
        assert r.get("status") == "ok", f"Expected status=ok, got: {r}"
        assert r.get("value") == 42

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_chat_stream(self):
        """流式输出"""
        from src.services.llm_service import llm_service
        chunks = []
        async for chunk in llm_service.chat_stream(
            messages=[{"role": "user", "content": "Count: 1 2 3"}],
            provider="deepseek",
            max_tokens=30,
        ):
            chunks.append(chunk)
        full = "".join(chunks)
        assert len(full) > 0, "Stream should produce output"
        assert any(c in full for c in "123"), f"Expected numbers in: {full[:50]}"

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """熔断器基本功能"""
        from src.services.llm_service import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
        assert not cb.is_open("test")
        cb.record_failure("test")
        assert not cb.is_open("test")
        cb.record_failure("test")
        assert cb.is_open("test")
        cb.record_success("test")
        assert not cb.is_open("test")


# ══════════════════════════════════════════
# 2. Companion Agent (伴读对话)
# ══════════════════════════════════════════

class TestCompanionAgentLLM:
    """伴读 Agent LLM 路径"""

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_companion_chat(self):
        """伴读对话生成"""
        from src.agent.companion_agent import CompanionAgent
        agent = CompanionAgent()
        # 先创建会话
        sess = await agent.execute({
            "action": "start_session",
            "user_id": "test-user",
            "lang": "en",
            "persona": {"level": "B1", "weak_areas": ["grammar"]},
        })
        assert "error" not in sess, f"Start session failed: {sess}"
        session_id = sess.get("session_id")
        assert session_id, f"Should have session_id: {sess}"
        # 发消息
        r = await agent.execute({
            "action": "send_message",
            "user_id": "test-user",
            "message": "Hello, can you help me practice English?",
            "lang": "en",
            "session_id": session_id,
            "persona": {"level": "B1", "weak_areas": ["grammar"]},
        })
        assert "error" not in r, f"Got error: {r}"
        assert "reply" in r, "Should have reply"

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_companion_correction(self):
        """伴读纠错"""
        from src.agent.companion_agent import CompanionAgent
        agent = CompanionAgent()
        sess = await agent.execute({
            "action": "start_session",
            "user_id": "test-user",
            "lang": "en",
            "persona": {"level": "B1"},
        })
        if "error" in sess:
            pytest.skip(f"Start session failed: {sess}")
        r = await agent.execute({
            "action": "send_message",
            "user_id": "test-user",
            "message": "I goes to school yesterday.",
            "lang": "en",
            "session_id": sess.get("session_id"),
            "persona": {"level": "B1"},
        })
        assert "error" not in r, f"Got error: {r}"
        assert r.get("reply") or r.get("correction"), f"Should have reply: {r}"


# ══════════════════════════════════════════
# 3. Assessment Agent (评估)
# ══════════════════════════════════════════

class TestAssessmentAgentLLM:
    """评估 Agent LLM 路径"""

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_generate_question(self):
        """生成评估题目"""
        from src.agent.assessment_agent import AssessmentAgent
        agent = AssessmentAgent()
        r = await agent.execute({
            "action": "generate_question",
            "user_id": "test-user",
            "lang": "en",
            "dimension": "grammar",
            "current_level_estimate": "B1",
            "assessment_id": None,
        })
        assert "error" not in r, f"Got error: {r}"
        assert "question" in r, "Should have question"

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_submit_answer(self):
        """提交答案评分"""
        from src.agent.assessment_agent import AssessmentAgent
        agent = AssessmentAgent()
        # 先生成题目
        q = await agent.execute({
            "action": "generate_question",
            "user_id": "test-user",
            "lang": "en",
            "dimension": "vocabulary",
            "current_level_estimate": "A2",
            "assessment_id": None,
        })
        if "error" in q:
            pytest.skip(f"Question generation failed: {q['error']}")

        # 提交答案
        r = await agent.execute({
            "action": "submit_answer",
            "user_id": "test-user",
            "assessment_id": q.get("assessment_id") or q.get("session_id"),
            "question_id": q.get("question_id", "q0"),
            "user_answer": "test answer",
        })
        assert "error" not in r, f"Got error: {r}"


# ══════════════════════════════════════════
# 4. Tutor Agent (导师)
# ══════════════════════════════════════════

class TestTutorAgentLLM:
    """导师 Agent LLM 路径"""

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_tutor_chat(self):
        """导师对话"""
        from src.agent.tutor_agent import TutorAgent
        agent = TutorAgent()
        r = await agent.execute({
            "action": "chat",
            "user_id": "test-user",
            "message": "Explain present perfect tense in one sentence.",
            "lang": "en",
        })
        assert "error" not in r, f"Got error: {r}"
        assert "reply" in r, f"Should have reply: {r}"

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_tutor_lesson(self):
        """生成课程"""
        from src.agent.tutor_agent import TutorAgent
        agent = TutorAgent()
        r = await agent.execute({
            "action": "lesson",
            "user_id": "test-user",
            "lang": "en",
            "topic": "past tense",
            "level": "A2",
        })
        assert "error" not in r, f"Got error: {r}"


# ══════════════════════════════════════════
# 5. Persona Agent (画像推断)
# ══════════════════════════════════════════

class TestPersonaAgentLLM:
    """画像 Agent LLM 路径"""

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_generate_persona(self):
        """生成初始画像"""
        from src.agent.persona_agent import PersonaAgent
        agent = PersonaAgent()
        r = await agent.execute({
            "action": "analyze_persona",
            "user_id": "test-user",
            "lang": "en",
            "dimension_scores": {
                "grammar": {"average_score": 6.5, "correct_rate": 0.7},
                "vocabulary": {"average_score": 8.0, "correct_rate": 0.85},
                "reading": {"average_score": 5.0, "correct_rate": 0.55},
            },
        })
        assert "error" not in r, f"Got error: {r}"
        assert "persona" in r, "Should have persona"

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_update_persona_local(self):
        """本地更新画像（不依赖LLM）"""
        from src.agent.persona_agent import PersonaAgent
        agent = PersonaAgent()
        r = await agent.update_persona({
            "existing_persona": {
                "strengths": [], "weaknesses": ["grammar"],
                "current_level": "A2", "learning_style": {"primary": "visual"},
                "skill_tree": {}, "interests": ["travel"], "total_study_minutes": 100
            },
            "new_dimension_scores": {
                "grammar": {"average_score": 8.5},
                "reading": {"average_score": 4.0}
            },
            "new_level": "B1",
            "study_minutes_delta": 45,
        })
        assert r["changed"], "Should have changes"
        assert "grammar" in r["persona"]["strengths"]


# ══════════════════════════════════════════
# 6. Plan Agent (计划生成)
# ══════════════════════════════════════════

class TestPlanAgentLLM:
    """计划 Agent LLM 路径"""

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_generate_plan(self):
        """生成学习计划"""
        from src.agent.plan_agent import PlanAgent
        agent = PlanAgent()
        r = await agent.execute({
            "action": "generate_plan",
            "user_id": "test-user",
            "lang": "en",
            "persona": {
                "current_level": "B1",
                "strengths": ["vocabulary"],
                "weaknesses": ["grammar", "writing"],
                "learning_style": {"primary": "visual"},
            },
        })
        assert "error" not in r, f"Got error: {r}"
        assert r.get("plan") or r.get("tasks"), f"Should have plan/tasks: {r}"

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_adjust_plan_local(self):
        """本地调整计划（不依赖LLM）"""
        from src.agent.plan_agent import PlanAgent
        agent = PlanAgent()
        r = await agent.adjust_plan({
            "current_plan": {"meta": {"daily_minutes": 30}},
            "completion_stats": {"total_tasks": 7, "completed": 2, "avg_rating": 2.5, "total_minutes": 100},
            "weak_areas": ["grammar", "writing"],
            "level": "B1",
        })
        assert len(r["adjustments"]) >= 3, f"Expected 3+ adjustments: {r}"


# ══════════════════════════════════════════
# 7. Help Agent (求助)
# ══════════════════════════════════════════

class TestHelpAgentLLM:
    """求助 Agent LLM 路径"""

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_help_request(self):
        """创建求助"""
        from src.agent.help_agent import HelpAgent
        agent = HelpAgent()
        r = await agent.execute({
            "action": "request",
            "user_id": "test-user",
            "lang": "en",
            "content": "Can someone explain the difference between 'affect' and 'effect'?",
        })
        assert "error" not in r, f"Got error: {r}"


# ══════════════════════════════════════════
# 8. 端到端：完整学习流程
# ══════════════════════════════════════════

class TestE2ELearning:
    """端到端学习流程"""

    @requires_deepseek
    @pytest.mark.asyncio
    async def test_full_cycle(self):
        """完整学习周期: 评估 → 画像 → 计划 → 伴读"""
        from src.agent.assessment_agent import AssessmentAgent
        from src.agent.persona_agent import PersonaAgent
        from src.agent.plan_agent import PlanAgent
        from src.agent.companion_agent import CompanionAgent

        user_id = "e2e-test-user"
        lang = "en"

        # Step 1: 评估
        print("\n📝 Step 1: Assessment")
        assess = AssessmentAgent()
        q = await assess.execute({
            "action": "generate_question",
            "user_id": user_id, "lang": lang,
            "dimension": "grammar",
            "current_level_estimate": "B1",
            "assessment_id": None,
        })
        assert "error" not in q, f"Assessment gen failed: {q}"

        # Step 2: 画像
        print("🧠 Step 2: Persona")
        persona = PersonaAgent()
        p = await persona.execute({
            "action": "generate_persona",
            "user_id": user_id, "lang": lang,
            "dimension_scores": {
                "grammar": {"average_score": 7.0, "correct_rate": 0.75},
                "vocabulary": {"average_score": 8.5, "correct_rate": 0.9},
            },
        })
        assert "error" not in p, f"Persona gen failed: {p}"

        # Step 3: 计划
        print("📋 Step 3: Plan")
        plan = PlanAgent()
        pl = await plan.execute({
            "action": "generate_plan",
            "user_id": user_id, "lang": lang,
            "persona": p.get("persona", {"current_level": "B1"}),
        })
        assert "error" not in pl, f"Plan gen failed: {pl}"

        # Step 4: 伴读
        print("💬 Step 4: Companion chat")
        companion = CompanionAgent()
        cs = await companion.execute({
            "action": "start_session",
            "user_id": user_id, "lang": lang,
            "persona": p.get("persona", {"level": "B1"}),
        })
        assert "error" not in cs, f"Companion start failed: {cs}"
        c = await companion.execute({
            "action": "send_message",
            "user_id": user_id,
            "message": "Hi! Let's practice.",
            "lang": lang,
            "session_id": cs.get("session_id"),
            "persona": p.get("persona", {"level": "B1"}),
        })
        assert "error" not in c, f"Companion failed: {c}"
        print("✅ E2E cycle complete!")


# ══════════════════════════════════════════
# 可直接运行的 smoke test
# ══════════════════════════════════════════
if __name__ == "__main__":
    async def smoke():
        """快速冒烟：验证 DeepSeek 连通性"""
        import httpx
        key = os.environ.get("LLM_DEEPSEEK_KEY", "")
        if not key:
            print("⚠️  LLM_DEEPSEEK_KEY not set")
            return
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 10},
            )
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            print(f"DeepSeek: {content}")
            print("✅ DeepSeek 集成测试连通！" if "OK" in content else f"⚠️ Unexpected: {content}")

    asyncio.run(smoke())
