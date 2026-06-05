"""
LAWA LLM 配置管理 Agent

功能：
- 添加自定义 LLM Provider（兼容 OpenAI / Anthropic 格式）
- 测试 Provider 连通性
- 列出所有 Provider 及状态
- 删除 Provider
- 设置默认 Provider
"""
import asyncio
import hashlib
import time
from typing import Optional
from loguru import logger
from src.agent.base_agent import BaseAgent


class LLMConfigAgent(BaseAgent):
    """LLM 配置管理 Agent"""

    def __init__(self):
        super().__init__("LLMConfigAgent")
        self.timeout_seconds = 30
        self.requires_persistence = False
        # 内存存储自定义 Provider（重启后需重新配置，或后续持久化到 DB）
        self._custom_providers: dict[str, dict] = {}
        self._provider_status: dict[str, dict] = {}  # name → {available, last_check, latency_ms}

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "list")
        handlers = {
            "add": self.add_provider,
            "test": self.test_provider,
            "list": self.list_providers,
            "remove": self.remove_provider,
            "set_default": self.set_default,
            "edit": self.edit_provider,
            "status": self.get_status,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    async def add_provider(self, payload: dict) -> dict:
        """
        添加自定义 LLM Provider

        payload:
        {
            "name": "my-deepseek",        # 唯一标识
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-xxx",
            "model": "deepseek-chat",
            "provider_type": "openai",     # "openai" | "anthropic"
        }
        """
        name = payload.get("name", "").strip()
        base_url = payload.get("base_url", "").strip()
        api_key = payload.get("api_key", "").strip()
        model = payload.get("model", "").strip()
        provider_type = payload.get("provider_type", "openai").strip()

        if not name:
            return {"error": "name is required"}
        if not base_url:
            return {"error": "base_url is required"}
        if not api_key:
            return {"error": "api_key is required"}
        if not model:
            return {"error": "model is required"}
        if provider_type not in ("openai", "anthropic"):
            return {"error": "provider_type must be 'openai' or 'anthropic'"}

        # 存储（API Key 脱敏存储）
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:12]
        self._custom_providers[name] = {
            "name": name,
            "base_url": base_url,
            "api_key": api_key,  # 明文存储于内存，重启丢失
            "model": model,
            "provider_type": provider_type,
            "key_hash": key_hash,
            "added_at": time.time(),
        }

        logger.info(f"LLM Provider 已添加: {name} ({base_url}) model={model}")

        # 自动测试连通性
        test_result = await self._ping_provider(name)

        return {
            "message": f"Provider '{name}' 已添加",
            "name": name,
            "base_url": base_url,
            "model": model,
            "provider_type": provider_type,
            "key_hash": key_hash,
            "status": test_result,
        }

    async def test_provider(self, payload: dict) -> dict:
        """
        测试 Provider 连通性

        payload:
        {
            "name": "my-deepseek",    # 已注册的 provider name
            # 或者直接传临时配置：
            "base_url": "...",
            "api_key": "...",
            "model": "...",
            "provider_type": "openai",
        }
        """
        name = payload.get("name")
        if name and name in self._custom_providers:
            return await self._ping_provider(name)
        elif payload.get("base_url") and payload.get("api_key"):
            # 临时测试（不保存）
            tmp_name = f"_tmp_{int(time.time())}"
            self._custom_providers[tmp_name] = {
                "name": tmp_name,
                "base_url": payload["base_url"],
                "api_key": payload["api_key"],
                "model": payload.get("model", "default"),
                "provider_type": payload.get("provider_type", "openai"),
                "key_hash": "",
                "added_at": time.time(),
            }
            result = await self._ping_provider(tmp_name)
            del self._custom_providers[tmp_name]
            return result
        else:
            return {"error": "Provide 'name' or 'base_url'+'api_key' to test"}

    async def _ping_provider(self, name: str) -> dict:
        """Ping 一个 Provider，返回可用状态"""
        provider = self._custom_providers.get(name)
        if not provider:
            return {"error": f"Provider '{name}' not found"}

        base_url = provider["base_url"]
        api_key = provider["api_key"]
        model = provider["model"]
        ptype = provider["provider_type"]

        start = time.time()
        try:
            if ptype == "anthropic":
                import httpx
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.post(
                        f"{base_url.rstrip('/')}/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "Content-Type": "application/json",
                            "anthropic-version": "2023-06-01",
                        },
                        json={
                            "model": model,
                            "max_tokens": 5,
                            "messages": [{"role": "user", "content": "Hi"}],
                        },
                    )
                    latency = round((time.time() - start) * 1000)
                    if r.status_code == 200:
                        status = {"available": True, "latency_ms": latency, "status_code": r.status_code}
                    else:
                        status = {"available": False, "latency_ms": latency, "status_code": r.status_code, "error": r.text[:200]}
            else:
                # OpenAI 兼容
                import httpx
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.post(
                        f"{base_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={"model": model, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5},
                    )
                    latency = round((time.time() - start) * 1000)
                    if r.status_code == 200:
                        status = {"available": True, "latency_ms": latency, "status_code": r.status_code}
                    else:
                        status = {"available": False, "latency_ms": latency, "status_code": r.status_code, "error": r.text[:200]}

        except Exception as e:
            latency = round((time.time() - start) * 1000)
            status = {"available": False, "latency_ms": latency, "error": str(e)[:200]}

        self._provider_status[name] = {**status, "last_check": time.time()}
        return {"name": name, **status}

    async def list_providers(self, payload: dict = None) -> dict:
        """列出所有自定义 Provider"""
        providers = []
        for name, p in self._custom_providers.items():
            status = self._provider_status.get(name, {})
            providers.append({
                "name": name,
                "base_url": p["base_url"],
                "model": p["model"],
                "provider_type": p["provider_type"],
                "key_hash": p["key_hash"],
                "available": status.get("available"),
                "latency_ms": status.get("latency_ms"),
                "last_check": status.get("last_check"),
            })
        return {"providers": providers, "count": len(providers)}

    async def remove_provider(self, payload: dict) -> dict:
        name = payload.get("name", "").strip()
        if not name:
            return {"error": "name is required"}
        if name not in self._custom_providers:
            return {"error": f"Provider '{name}' not found"}
        del self._custom_providers[name]
        self._provider_status.pop(name, None)
        logger.info(f"LLM Provider 已删除: {name}")
        return {"message": f"Provider '{name}' 已删除"}

    async def set_default(self, payload: dict) -> dict:
        """设置默认 Provider（影响 llm_service 的路由优先级）"""
        name = payload.get("name", "").strip()
        if not name:
            return {"error": "name is required"}
        if name not in self._custom_providers:
            return {"error": f"Provider '{name}' not found"}
        # 存储默认标记
        self._default_provider = name
        logger.info(f"默认 LLM Provider 已切换为: {name}")
        return {"message": f"默认 Provider 已切换为 '{name}'", "default": name}

    async def edit_provider(self, payload: dict) -> dict:
        """编辑已注册的 Provider"""
        name = payload.get("name", "").strip()
        if not name:
            return {"error": "name is required"}
        if name not in self._custom_providers:
            return {"error": f"Provider '{name}' not found"}
        
        provider = self._custom_providers[name]
        updated = False
        if payload.get("api_key"):
            provider["api_key"] = payload["api_key"]
            provider["key_hash"] = hashlib.sha256(payload["api_key"].encode()).hexdigest()[:12]
            updated = True
        if payload.get("base_url"):
            provider["base_url"] = payload["base_url"]
            updated = True
        if payload.get("model"):
            provider["model"] = payload["model"]
            updated = True
        if payload.get("provider_type"):
            provider["provider_type"] = payload["provider_type"]
            updated = True
        
        if not updated:
            return {"error": "No fields to update"}
        
        logger.info(f"LLM Provider 已更新: {name}")
        return {"message": f"Provider '{name}' 已更新", "name": name, "base_url": provider["base_url"], "model": provider["model"]}

    async def get_status(self, payload: dict = None) -> dict:
        """获取所有 Provider 状态（含自动 ping）"""
        results = []
        for name in self._custom_providers:
            status = await self._ping_provider(name)
            results.append(status)
        available = sum(1 for r in results if r.get("available"))
        return {"providers": results, "total": len(results), "available": available}


# 全局单例
llm_config_agent = LLMConfigAgent()
