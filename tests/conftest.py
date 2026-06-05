"""
Pytest fixtures: async test client + in-memory SQLite database
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 在导入任何 src 模块前设置测试环境变量
os.environ["DB_USE_SQLITE"] = "true"
os.environ["SQLITE_PATH"] = ":memory:"
os.environ["JWT_SECRET"] = "test-secret-for-pytest"
os.environ["DEBUG"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["LLM_NVIDIA_KEY"] = ""
os.environ["LLM_OPENCODE_KEY"] = ""

from src.database import engine, Base, AsyncSessionLocal, get_db
from src.main import app


@pytest.fixture(scope="session")
def event_loop():
    """创建 session 级事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def setup_db():
    """每个需要DB的测试前重建表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(setup_db):
    """异步数据库会话"""
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(setup_db):
    """Async HTTP TestClient"""
    async def override_get_db():
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def user_payload():
    """标准测试用户注册数据"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePass123!",
        "native_lang": "zh",
        "learn_lang": "en",
    }


@pytest_asyncio.fixture
async def auth_client(client, user_payload):
    """已注册+登录的客户端"""
    resp = await client.post("/api/v1/auth/register", json=user_payload)
    assert resp.status_code == 201, f"注册失败: {resp.json()}"
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
