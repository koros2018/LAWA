"""
LAWA 缓存服务

- 内存缓存（默认，无依赖）
- Redis 缓存（可选，生产环境）
- 装饰器模式，对业务代码零侵入
"""
import asyncio
import hashlib
import json
import time
from functools import wraps
from typing import Any, Optional, Callable
from loguru import logger


class MemoryCache:
    """线程安全的内存缓存（带 TTL）"""

    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expire_at)
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expire_at = entry
            if time.monotonic() > expire_at:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            if len(self._store) >= self._max_size:
                # 淘汰最老的 20%
                sorted_keys = sorted(self._store, key=lambda k: self._store[k][1])
                for old_key in sorted_keys[: self._max_size // 5]:
                    del self._store[old_key]
            expire_at = time.monotonic() + (ttl or self._default_ttl)
            self._store[key] = (value, expire_at)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> int:
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    async def invalidate_pattern(self, pattern: str) -> int:
        """删除所有匹配 pattern 的 key（简单子串匹配）"""
        async with self._lock:
            keys_to_del = [k for k in self._store if pattern in k]
            for k in keys_to_del:
                del self._store[k]
            return len(keys_to_del)


class RedisCache:
    """Redis 缓存（需要 redis-py）"""

    def __init__(self, redis_url: str, default_ttl: int = 300):
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(self._redis_url, decode_responses=True)
                await self._client.ping()
                logger.info("✅ Redis 缓存已连接")
            except Exception as e:
                logger.warning(f"Redis 连接失败，降级到内存缓存: {e}")
                raise
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        try:
            client = await self._get_client()
            raw = await client.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        try:
            client = await self._get_client()
            await client.set(key, json.dumps(value, default=str), ex=ttl or self._default_ttl)
        except Exception:
            pass

    async def delete(self, key: str) -> bool:
        try:
            client = await self._get_client()
            return await client.delete(key) > 0
        except Exception:
            return False

    async def clear(self) -> int:
        try:
            client = await self._get_client()
            keys = await client.keys("lawa:*")
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception:
            return 0

    async def invalidate_pattern(self, pattern: str) -> int:
        try:
            client = await self._get_client()
            keys = await client.keys(f"lawa:*{pattern}*")
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception:
            return None


class CacheService:
    """
    统一缓存服务
    优先 Redis，降级内存
    """

    def __init__(self, redis_url: Optional[str] = None, default_ttl: int = 300):
        self._memory = MemoryCache(default_ttl=default_ttl)
        self._redis: Optional[RedisCache] = None
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._using_redis = False

    async def init(self) -> None:
        """尝试连接 Redis，失败则降级内存"""
        if self._redis_url:
            try:
                self._redis = RedisCache(self._redis_url, self._default_ttl)
                await self._redis._get_client()
                self._using_redis = True
                logger.info("✅ 缓存服务: Redis 模式")
                return
            except Exception:
                logger.warning("Redis 不可用，使用内存缓存")
        logger.info("✅ 缓存服务: 内存模式")

    async def get(self, key: str) -> Optional[Any]:
        if self._using_redis and self._redis:
            result = await self._redis.get(key)
            if result is not None:
                return result
        return await self._memory.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if self._using_redis and self._redis:
            await self._redis.set(key, value, ttl)
        await self._memory.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        r1 = await self._memory.delete(key) if not self._using_redis else False
        r2 = await self._redis.delete(key) if self._using_redis and self._redis else False
        return r1 or r2

    async def invalidate(self, pattern: str) -> int:
        count = 0
        if self._using_redis and self._redis:
            count += await self._redis.invalidate_pattern(pattern) or 0
        count += await self._memory.invalidate_pattern(pattern)
        return count

    @staticmethod
    def make_key(*parts: str) -> str:
        """生成缓存 key"""
        return "lawa:" + ":".join(str(p) for p in parts)

    @staticmethod
    def hash_key(prefix: str, data: Any) -> str:
        """对复杂对象生成 hash key"""
        raw = json.dumps(data, sort_keys=True, default=str)
        h = hashlib.md5(raw.encode()).hexdigest()[:12]
        return f"lawa:{prefix}:{h}"


def cached(prefix: str, ttl: int = 300, key_fn: Optional[Callable] = None):
    """
    缓存装饰器（用于 async 函数）

    用法:
        @cached("leaderboard", ttl=60)
        async def get_leaderboard(self, lang: str, period: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            cache = getattr(self, "_cache", None)
            if cache is None:
                return await func(self, *args, **kwargs)

            if key_fn:
                cache_key = key_fn(*args, **kwargs)
            else:
                key_parts = [prefix] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
                cache_key = CacheService.make_key(*key_parts)

            # 尝试读缓存
            cached_val = await cache.get(cache_key)
            if cached_val is not None:
                logger.debug(f"缓存命中: {cache_key}")
                return cached_val

            # 执行原函数
            result = await func(self, *args, **kwargs)
            await cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


# 全局单例
cache_service = CacheService()
