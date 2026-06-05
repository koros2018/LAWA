"""
LAWA LLM 配置管理 API 路由

端点：
- POST /api/v1/llm-config/add        — 添加自定义 Provider
- POST /api/v1/llm-config/test       — 测试 Provider 连通性
- GET  /api/v1/llm-config/list       — 列出所有 Provider
- DELETE /api/v1/llm-config/remove   — 删除 Provider
- POST /api/v1/llm-config/set-default — 设置默认 Provider
- GET  /api/v1/llm-config/status     — 获取所有 Provider 状态
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from src.agent.llm_config_agent import llm_config_agent
from src.services.llm_service import llm_service

router = APIRouter(prefix="/api/v1/llm-config", tags=["LLM配置"])


class AddProviderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Provider 唯一标识")
    base_url: str = Field(..., description="API Base URL")
    api_key: str = Field(..., description="API Key")
    model: str = Field(..., description="模型名称")
    provider_type: str = Field(default="openai", pattern="^(openai|anthropic)$")


class TestProviderRequest(BaseModel):
    name: Optional[str] = Field(None, description="已注册的 Provider name")
    base_url: Optional[str] = Field(None, description="临时测试用 Base URL")
    api_key: Optional[str] = Field(None, description="临时测试用 API Key")
    model: Optional[str] = Field("default", description="临时测试用模型")
    provider_type: Optional[str] = Field("openai", pattern="^(openai|anthropic)$")


class RemoveProviderRequest(BaseModel):
    name: str

class EditProviderRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="API Key (留空保持不变)")
    base_url: Optional[str] = Field(None, description="API Base URL")
    model: Optional[str] = Field(None, description="模型名称")
    provider_type: Optional[str] = Field(None, pattern="^(openai|anthropic)$")


class SetDefaultRequest(BaseModel):
    name: str


@router.post("/add")
async def add_provider(req: AddProviderRequest):
    result = await llm_config_agent.execute({
        "action": "add",
        "name": req.name,
        "base_url": req.base_url,
        "api_key": req.api_key,
        "model": req.model,
        "provider_type": req.provider_type,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/test")
async def test_provider(req: TestProviderRequest):
    # 优先走自定义 provider，若 name 不在自定义列表则从 llm_service 取配置
    result = await llm_config_agent.execute({
        "action": "test",
        "name": req.name,
        "base_url": req.base_url,
        "api_key": req.api_key,
        "model": req.model,
        "provider_type": req.provider_type,
    })
    if "error" in result and req.name and req.name in llm_service._provider_configs:
        # fallback: 用 llm_service 的配置直接 ping
        cfg = llm_service._provider_configs[req.name]
        tmp_name = f"_tmp_{req.name}"
        llm_config_agent._custom_providers[tmp_name] = {
            "name": tmp_name,
            "base_url": cfg["base_url"],
            "api_key": cfg["key"],
            "model": cfg["model"],
            "provider_type": "openai",
            "key_hash": "",
            "added_at": 0,
        }
        result = await llm_config_agent._ping_provider(tmp_name)
        del llm_config_agent._custom_providers[tmp_name]
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/list")
async def list_providers():
    result = await llm_config_agent.execute({"action": "list"})
    # 合并 llm_service 中已初始化但不在自定义列表的 provider
    existing_names = {p["name"] for p in result.get("providers", [])}
    for name, cfg in llm_service._provider_configs.items():
        if name not in existing_names:
            result["providers"].append({
                "name": name,
                "base_url": cfg["base_url"],
                "model": cfg["model"],
                "provider_type": "openai",
                "key_hash": "***",
                "available": name in llm_service._clients,
                "latency_ms": None,
                "last_check": None,
            })
    result["count"] = len(result["providers"])
    return result


@router.delete("/remove")
async def remove_provider(req: RemoveProviderRequest):
    result = await llm_config_agent.execute({"action": "remove", "name": req.name})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/set-default")
async def set_default(req: SetDefaultRequest):
    result = await llm_config_agent.execute({"action": "set_default", "name": req.name})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.put("/edit/{name}")
async def edit_provider(name: str, req: EditProviderRequest):
    """编辑已注册的 Provider"""
    payload: dict = {"action": "edit", "name": name}
    if req.api_key is not None: payload["api_key"] = req.api_key
    if req.base_url is not None: payload["base_url"] = req.base_url
    if req.model is not None: payload["model"] = req.model
    if req.provider_type is not None: payload["provider_type"] = req.provider_type
    result = await llm_config_agent.execute(payload)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/status")
async def get_status():
    result = await llm_config_agent.execute({"action": "status"})
    existing_names = {p["name"] for p in result.get("providers", [])}
    for name, cfg in llm_service._provider_configs.items():
        if name not in existing_names:
            result["providers"].append({
                "name": name,
                "base_url": cfg["base_url"],
                "model": cfg["model"],
                "available": name in llm_service._clients,
                "latency_ms": None,
                "last_check": None,
            })
    result["total"] = len(result["providers"])
    result["available"] = sum(1 for p in result["providers"] if p.get("available"))
    return result
