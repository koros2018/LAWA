"""
LAWA LLM 服务封装

多模型提供商支持：
- LongCat (LongCat-2.0-Preview)
- OpenCode (kimi-k2.6)
- Ollama (本地兜底)

功能：
- 多Provider路由 + 自动故障转移
- 异步调用 + 超时 + 重试
- 流式响应
- 结构化JSON输出
"""
import asyncio
import time
from typing import Optional, AsyncGenerator
from openai import AsyncOpenAI
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.config import settings


class CircuitBreaker:
    """熔断器 — 当Provider连续失败N次后，暂停使用一段时间"""
    
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures: dict[str, int] = {}       # provider → consecutive failures
        self._open_until: dict[str, float] = {}   # provider → timestamp until circuit is open
    
    def is_open(self, provider: str) -> bool:
        """检查熔断器是否打开（是否应该拒绝请求）"""
        if provider not in self._open_until:
            return False
        if time.time() > self._open_until[provider]:
            # 冷却期已过，半开状态（允许一次尝试）
            del self._open_until[provider]
            return False
        return True
    
    def record_success(self, provider: str):
        """记录成功，重置失败计数"""
        self._failures[provider] = 0
        self._open_until.pop(provider, None)
    
    def record_failure(self, provider: str):
        """记录失败，达到阈值则打开熔断器"""
        self._failures[provider] = self._failures.get(provider, 0) + 1
        if self._failures[provider] >= self.failure_threshold:
            self._open_until[provider] = time.time() + self.cooldown_seconds
            logger.warning(f"🔌 熔断器打开: {provider} (连续失败{self._failures[provider]}次, {self.cooldown_seconds}s冷却)")
    
    def status(self) -> dict:
        """返回所有Provider的熔断器状态"""
        result = {}
        for provider in self._failures:
            result[provider] = {
                "failures": self._failures[provider],
                "open": self.is_open(provider),
                "cooldown_remaining": max(0, self._open_until.get(provider, 0) - time.time())
            }
        return result


class LLMService:
    """统一LLM服务 - 多Provider支持"""

    def __init__(self):
        self._clients: dict[str, AsyncOpenAI] = {}
        self._provider_configs: dict[str, dict] = {}
        self._breaker = CircuitBreaker()
        self._init_providers()

    def _add_provider(self, name: str, key: Optional[str], base_url: str, model: str):
        """注册一个LLM提供商"""
        if not key:
            logger.debug(f"跳过未配置的提供商: {name}")
            return

        self._provider_configs[name] = {
            "key": key,
            "base_url": base_url,
            "model": model,
        }

        self._clients[name] = AsyncOpenAI(
            api_key=key,
            base_url=base_url,
            timeout=settings.llm_timeout_seconds,
        )
        logger.info(f"✅ LLM Provider: {name} ({base_url[:40]}...) model={model}")

    def _init_providers(self):
        """初始化所有提供商"""
        # LongCat
        self._add_provider(
            "longcat",
            settings.llm_longcat_key,
            settings.llm_longcat_base_url,
            settings.llm_longcat_model,
        )

        # OpenCode (kimi-k2.6)
        self._add_provider(
            "opencode",
            settings.llm_opencode_key,
            settings.llm_opencode_base_url,
            settings.llm_opencode_model,
        )

        # Ollama 始终可用（兜底）
        self._clients["ollama"] = AsyncOpenAI(
            api_key="ollama",
            base_url=f"{settings.ollama_host}/v1",
            timeout=settings.llm_timeout_seconds,
        )
        self._provider_configs["ollama"] = {
            "key": "ollama",
            "base_url": f"{settings.ollama_host}/v1",
            "model": settings.ollama_model,
        }
        logger.info(f"✅ LLM Provider: ollama ({settings.ollama_host}) model={settings.ollama_model}")

        # DeepSeek
        self._add_provider(
            "deepseek",
            settings.llm_deepseek_key,
            settings.llm_deepseek_base_url,
            settings.llm_deepseek_model,
        )

        if not self._provider_configs:
            logger.warning("⚠️ 未配置任何云LLM提供商，将仅使用Ollama本地模型")

    def _get_client(self, provider: str) -> AsyncOpenAI:
        """获取Provider客户端"""
        if provider not in self._clients:
            logger.warning(f"Provider {provider} 不可用，切换到 ollama")
            provider = "ollama"
        return self._clients[provider]

    def _get_model(self, provider: str) -> str:
        """获取Provider默认模型"""
        return self._provider_configs.get(provider, {}).get("model", settings.ollama_model)

    @property
    def available_providers(self) -> list[str]:
        """列出可用提供商"""
        return list(self._clients.keys())

    @property
    def default_provider(self) -> str:
        """默认提供商（优先云LLM）"""
        for p in ["longcat", "opencode"]:
            if p in self._clients:
                return p
        return "ollama"

    @property
    def circuit_breaker_status(self) -> dict:
        """返回所有Provider的熔断器状态"""
        return self._breaker.status()

    # ── 任务 → 提供商的路由策略 ──
    TASK_ROUTING = {
        "assessment": ["longcat", "opencode", "ollama"],
        "companion": ["longcat", "opencode", "ollama"],
        "correction": ["longcat", "opencode", "ollama"],
        "planning": ["opencode", "longcat", "ollama"],
        "simple": ["opencode", "longcat", "ollama"],
    }

    def route_provider(self, task: str) -> str:
        """根据任务类型选择合适的Provider（带故障转移）"""
        candidates = self.TASK_ROUTING.get(task, ["longcat", "opencode", "ollama"])
        for provider in candidates:
            if provider in self._clients:
                return provider
        return "ollama"

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((asyncio.TimeoutError, ConnectionError)),
    )
    async def chat(
        self,
        messages: list[dict],
        task: str = "companion",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> str:
        """同步LLM调用（含熔断器保护）"""
        provider = provider or self.route_provider(task)
        model = model or self._get_model(provider)
        client = self._get_client(provider)
        temp = temperature if temperature is not None else settings.llm_temperature
        max_tok = max_tokens or settings.llm_max_tokens

        # 熔断器检查 — 如果当前Provider熔断打开，直接故障转移
        if self._breaker.is_open(provider):
            logger.warning(f"🔌 熔断器阻止调用: {provider}")
            fallback = self._find_fallback(provider)
            if fallback and fallback != provider:
                logger.warning(f"故障转移: {provider} → {fallback}")
                return await self.chat(
                    messages=messages,
                    task=task,
                    provider=fallback,
                    model=None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
            raise RuntimeError(f"所有LLM Provider不可用（熔断器已触发: {provider}）")

        logger.info(f"LLM: [{provider}] {model} | task={task} | msgs={len(messages)} | temp={temp}")

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                max_tokens=max_tok,
                response_format=response_format,
            )
            content = response.choices[0].message.content or ""
            self._breaker.record_success(provider)
            logger.info(f"LLM response: {len(content)} chars | first 80: {content[:80]}")
            return content

        except Exception as e:
            logger.error(f"LLM [{provider}] 调用失败: {e}")
            self._breaker.record_failure(provider)
            # 故障转移到下一个Provider（跳过熔断打开的）
            fallback = self._find_fallback(provider)
            if fallback and fallback != provider:
                logger.warning(f"故障转移: {provider} → {fallback}")
                return await self.chat(
                    messages=messages,
                    task=task,
                    provider=fallback,
                    model=None,  # 用fallback的默认模型
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
            raise

    async def chat_stream(
        self,
        messages: list[dict],
        task: str = "companion",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式LLM调用（含熔断器保护）"""
        provider = provider or self.route_provider(task)
        model = model or self._get_model(provider)
        client = self._get_client(provider)
        temp = temperature if temperature is not None else settings.llm_temperature
        max_tok = max_tokens or settings.llm_max_tokens

        # 熔断器检查
        if self._breaker.is_open(provider):
            logger.warning(f"🔌 熔断器阻止流式调用: {provider}")
            raise RuntimeError(f"Provider {provider} 熔断器已打开")

        logger.info(f"LLM stream: [{provider}] {model} | task={task}")

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp,
                max_tokens=max_tok,
                stream=True,
            )
        except Exception as e:
            self._breaker.record_failure(provider)
            raise

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_json(
        self,
        messages: list[dict],
        task: str = "assessment",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> dict:
        """获取JSON格式响应"""
        import json

        response = await self.chat(
            messages=messages,
            task=task,
            provider=provider,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning(f"LLM返回非JSON: {response[:200]}")
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(response[start:end])
                except json.JSONDecodeError:
                    pass
            return {"error": "json_parse_failed", "raw": response[:500]}

    def _find_fallback(self, current_provider: str) -> Optional[str]:
        """找到下一个可用的Provider（跳过熔断打开的）"""
        providers = list(self._clients.keys())
        try:
            idx = providers.index(current_provider)
            for i in range(idx + 1, len(providers)):
                if not self._breaker.is_open(providers[i]):
                    return providers[i]
        except ValueError:
            pass
        # 从头查找（跳过当前provider和熔断打开的）
        for p in providers:
            if p != current_provider and not self._breaker.is_open(p):
                return p
        return None


# 全局单例
llm_service = LLMService()

# 启动时打印可用Provider
logger.info(f"🦝 LLM Providers: {llm_service.available_providers}")
logger.info(f"   默认: {llm_service.default_provider}")
