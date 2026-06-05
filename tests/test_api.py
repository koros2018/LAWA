"""
测试：API 端点 — 健康检查 + 认证流程
"""
import pytest


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_root_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "LAWA"

    @pytest.mark.asyncio
    async def test_api_health(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "database" in data


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, client, user_payload):
        resp = await client.post("/api/v1/auth/register", json=user_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"]

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client, user_payload):
        resp1 = await client.post("/api/v1/auth/register", json=user_payload)
        assert resp1.status_code == 201
        resp2 = await client.post("/api/v1/auth/register", json=user_payload)
        assert resp2.status_code == 409
        assert "已存在" in resp2.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, user_payload):
        await client.post("/api/v1/auth/register", json=user_payload)
        dup = {**user_payload, "username": "otheruser"}
        resp = await client.post("/api/v1/auth/register", json=dup)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_creates_profile(self, client, user_payload, db_session):
        from sqlalchemy import select
        from src.models.user import LawaProfile
        from src.models.coin import CoinTransaction

        resp = await client.post("/api/v1/auth/register", json=user_payload)
        assert resp.status_code == 201
        user_id = resp.json()["user_id"]

        profile = await db_session.execute(
            select(LawaProfile).where(LawaProfile.user_id == user_id)
        )
        profile = profile.scalar_one_or_none()
        assert profile is not None
        assert profile.native_lang == user_payload["native_lang"]
        assert profile.learn_lang == user_payload["learn_lang"]
        assert profile.total_coins == 1000

        txn = await db_session.execute(
            select(CoinTransaction).where(CoinTransaction.user_id == user_id)
        )
        txn = txn.scalar_one_or_none()
        assert txn is not None
        assert txn.amount == 1000
        assert txn.type == "register"


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client, user_payload):
        await client.post("/api/v1/auth/register", json=user_payload)
        resp = await client.post("/api/v1/auth/login", json={
            "username": user_payload["username"],
            "password": user_payload["password"],
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, user_payload):
        await client.post("/api/v1/auth/register", json=user_payload)
        resp = await client.post("/api/v1/auth/login", json={
            "username": user_payload["username"],
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/v1/auth/login", json={
            "username": "nobody",
            "password": "whatever",
        })
        assert resp.status_code == 401


class TestMe:
    @pytest.mark.asyncio
    async def test_me_authenticated(self, auth_client):
        resp = await auth_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_me_no_token(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_invalid_token(self, client):
        client.headers["Authorization"] = "Bearer invalid-token-here"
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_nonexistent_user(self, client):
        from src.utils.security import create_access_token
        import uuid
        client.headers["Authorization"] = f"Bearer {create_access_token(str(uuid.uuid4()))}"
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 404


class TestAuthFlow:
    @pytest.mark.asyncio
    async def test_full_register_login_me_flow(self, client, user_payload):
        # 1. 注册
        reg_resp = await client.post("/api/v1/auth/register", json=user_payload)
        assert reg_resp.status_code == 201
        token = reg_resp.json()["access_token"]

        # 2. 登录
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": user_payload["username"],
            "password": user_payload["password"],
        })
        assert login_resp.status_code == 200

        # 3. 获取个人信息
        client.headers["Authorization"] = f"Bearer {token}"
        me_resp = await client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == user_payload["username"]
