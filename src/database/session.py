"""
LAWA 数据库会话统一管理器

Agent 层统一通过 get_async_session() 获取会话，
保持与路由层 get_db() 一致的会话生命周期管理。

使用方式：
    async with get_async_session() as session:
        result = await session.execute(...)
        await session.commit()
"""
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import AsyncSessionLocal


async def get_async_session() -> AsyncSession:
    """获取异步数据库会话（Agent 层使用）
    
    返回一个可直接使用的 AsyncSession 实例，调用者负责 commit/rollback/close。
    与路由层 get_db() 使用同一个 AsyncSessionLocal，确保会话配置一致。
    """
    return AsyncSessionLocal()
