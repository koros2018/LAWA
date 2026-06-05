"""
LAWA BaseAgent

所有 Sub-Agent 的基类。
统一接口 + 生命周期 + 超时保护 + 持久化钩子。

生命周期：
  payload → execute() → _persist() → result
                ↓ (异常)
           _on_error() → error result
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
from loguru import logger
from src.config import settings


class BaseAgent(ABC):
    """Agent 基类

    子类只需要实现 execute(payload) → dict。
    超时保护、持久化、错误处理均自动生效。

    类属性（子类可覆盖）：
    - timeout_seconds: Agent 执行超时（默认 60s）
    - requires_persistence: 是否需要持久化（默认 True）
    """

    # ── 子类可覆盖的配置 ──
    timeout_seconds: int = 60
    requires_persistence: bool = True

    def __init__(self, name: str):
        self.name = name
        self.logger = logger.bind(agent=name)

    # ── 公共入口 ──
    async def run(self, payload: dict) -> dict:
        """对外统一入口：超时保护 + 执行 + 持久化 + 错误处理

        替代原始 execute() 作为路由层的调用入口。
        """
        try:
            result = await asyncio.wait_for(
                self.execute(payload),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            self.logger.error(f"[{self.name}] 超时 ({self.timeout_seconds}s)")
            error_result = {"error": "timeout", "message": f"Agent {self.name} 执行超时"}
            await self._on_error(payload, asyncio.TimeoutError())
            return error_result
        except Exception as e:
            self.logger.error(f"[{self.name}] 异常: {e}")
            error_result = {"error": "exception", "message": str(e)}
            await self._on_error(payload, e)
            return error_result

        # 持久化后置处理
        if self.requires_persistence and not result.get("error"):
            await self._persist(payload, result)

        self.log_execution(payload, result)
        return result

    # ── 子类必须实现 ──
    @abstractmethod
    async def execute(self, payload: dict) -> dict:
        """执行 Agent 主逻辑。子类必须实现。"""
        ...

    # ── 生命周期钩子（子类可选覆盖） ──
    async def _persist(self, payload: dict, result: dict) -> None:
        """持久化钩子：execute 成功后自动调用。

        子类应在此方法中写入数据库。
        基类默认行为：如果 payload 中有 db 且有未提交的变更，执行 commit。
        """
        db = payload.get("db")
        if db:
            try:
                await db.commit()
            except Exception as e:
                self.logger.warning(f"[{self.name}] _persist commit 失败: {e}")
                try:
                    await db.rollback()
                except Exception:
                    pass

    async def _on_error(self, payload: dict, error: Exception) -> None:
        """错误处理钩子：execute 异常时自动调用。

        子类可重写以添加自定义恢复逻辑。
        基类默认行为：回滚 DB 事务。
        """
        db = payload.get("db")
        if db:
            try:
                await db.rollback()
            except Exception:
                pass

    # ── LLM 调用封装 ──
    async def call_llm(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
    ) -> dict:
        """统一 LLM 调用接口"""
        model = model or settings.llm_default_provider
        temperature = temperature or settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_tokens

        self.logger.info(f"LLM call: model={model}, messages_count={len(messages)}")

        from src.services.llm_service import llm_service
        return await llm_service.chat_json(
            messages=messages,
            task="agent_call",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def log_execution(self, payload: dict, result: dict):
        """记录 Agent 执行日志"""
        self.logger.info(
            f"[{self.name}] executed | "
            f"payload_keys={list(payload.keys())} | "
            f"result_keys={list(result.keys())}"
        )

    # ── 兼容旧接口（deprecated，逐步迁移） ──
    async def execute_with_timeout(self, payload: dict, timeout_seconds: int = 60) -> dict:
        """@deprecated: 使用 run() 替代"""
        return await self.run(payload)
