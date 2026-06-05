"""
LAWA 伴读 API 路由

端点：
- GET  /api/v1/companion/scenarios       — 获取场景列表
- POST /api/v1/companion/session/start   — 启动伴读会话
- POST /api/v1/companion/session/message — 发送消息
- POST /api/v1/companion/session/end     — 结束会话
- GET  /api/v1/companion/session/{id}    — 获取会话详情
- GET  /api/v1/companion/sessions        — 列出用户会话
- POST /api/v1/companion/sessions/cleanup — 清理过期会话
- POST /api/v1/companion/scenario/generate — LLM 动态生成个性化场景
- POST /api/v1/companion/correct         — 单独纠错（不含对话）
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from src.agent.companion_agent import CompanionAgent
from src.services.correction import correction_engine

router = APIRouter(prefix="/api/v1/companion", tags=["AI伴读"])

# Agent 实例
companion_agent = CompanionAgent()


# ── 请求模型 ──
class StartSessionRequest(BaseModel):
    lang: str = Field(..., pattern="^(en|zh)$", description="语言: en/zh")
    user_id: Optional[str] = None
    scenario_id: Optional[str] = Field(None, description="场景ID，不传则随机")
    user_level: Optional[str] = Field("B1", description="用户水平: A1~C2 或 HSK1~6")


class SendMessageRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., min_length=1, description="用户消息")


class EndSessionRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")


class CorrectRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待纠错文本")
    lang: str = Field(..., pattern="^(en|zh)$")
    user_level: Optional[str] = Field("B1", description="用户水平")
    context: Optional[str] = Field(None, description="对话上下文（可选）")


class GetSessionRequest(BaseModel):
    session_id: str


class GenerateScenarioRequest(BaseModel):
    lang: str = Field(..., pattern="^(en|zh)$", description="语言: en/zh")
    user_level: Optional[str] = Field("B1", description="用户水平: A1~C2 或 HSK1~6")
    interest: Optional[str] = Field("daily_life", description="兴趣领域: travel/business/culture/daily_life/food/health/technology")
    topic: Optional[str] = Field(None, description="具体主题（可选）")


# ── API 端点 ──

@router.get("/scenarios")
async def list_scenarios(lang: str = Query("en", pattern="^(en|zh)$")):
    """获取场景列表"""
    result = await companion_agent.run({
        "action": "list_scenarios",
        "lang": lang,
    })
    return result


@router.post("/session/start")
async def start_session(req: StartSessionRequest):
    """启动新的伴读会话"""
    result = await companion_agent.run({
        "action": "start_session",
        "user_id": req.user_id,
        "lang": req.lang,
        "scenario_id": req.scenario_id,
        "user_level": req.user_level,
    })

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.post("/session/message")
async def send_message(req: SendMessageRequest):
    """发送对话消息"""
    result = await companion_agent.run({
        "action": "send_message",
        "session_id": req.session_id,
        "message": req.message,
    })

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.post("/session/end")
async def end_session(req: EndSessionRequest):
    """结束伴读会话"""
    result = await companion_agent.run({
        "action": "end_session",
        "session_id": req.session_id,
    })

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    result = await companion_agent.run({
        "action": "get_session",
        "session_id": session_id,
    })

    if "error" in result:
        raise HTTPException(404, result["error"])

    return result


@router.post("/scenario/generate")
async def generate_scenario(req: GenerateScenarioRequest):
    """LLM 动态生成个性化场景"""
    result = await companion_agent.run({
        "action": "generate_scenario",
        "lang": req.lang,
        "user_level": req.user_level,
        "interest": req.interest,
        "topic": req.topic,
    })
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result


@router.get("/sessions")
async def list_sessions(user_id: Optional[str] = None):
    """列出用户的所有会话"""
    result = await companion_agent.run({
        "action": "list_sessions",
        "user_id": user_id,
    })
    return result


class CleanupRequest(BaseModel):
    timeout_minutes: Optional[int] = Field(30, ge=5, le=1440, description="超时分钟数 (5~1440)")
    dry_run: Optional[bool] = Field(False, description="仅统计不执行")


@router.post("/sessions/cleanup")
async def cleanup_sessions(req: CleanupRequest = CleanupRequest()):
    """清理过期伴读会话（超时未活动 → 标记为 abandoned）"""
    result = await companion_agent.run({
        "action": "cleanup_stale",
        "timeout_minutes": req.timeout_minutes,
        "dry_run": req.dry_run,
    })
    return result


@router.post("/correct")
async def correct_text(req: CorrectRequest):
    """独立纠错接口（不含对话）"""
    context_messages = None
    if req.context:
        context_messages = [{"role": "user", "content": req.context}]

    result = await correction_engine.correct(
        user_message=req.text,
        lang=req.lang,
        user_level=req.user_level,
        context_messages=context_messages,
    )

    return {
        "original": req.text,
        **result,
    }
