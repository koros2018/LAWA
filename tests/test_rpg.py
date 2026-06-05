"""
测试：RPG 子系统集成 — 成就 / 文化活动 / 总架构师
"""
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def user_id(auth_client):
    """从注册响应中提取真实 user_id"""
    # auth_client 已经完成注册+登录，我们需要 user_id
    # 通过 /me 获取
    resp = await auth_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    return data["id"]


class TestAchievementSystem:
    """成就系统集成测试"""

    @pytest.mark.asyncio
    async def test_list_all_achievements(self, client):
        """无用户 — 列出所有成就模板"""
        resp = await client.get("/api/v1/rpg/achievements")
        assert resp.status_code == 200
        data = resp.json()
        assert "achievements" in data
        assert data["count"] > 0, "种子成就应该已入库"

    @pytest.mark.asyncio
    async def test_list_by_category(self, client):
        """按分类筛选"""
        resp = await client.get("/api/v1/rpg/achievements?category=milestone")
        assert resp.status_code == 200
        data = resp.json()
        for a in data["achievements"]:
            assert a["category"] == "milestone"

    @pytest.mark.asyncio
    async def test_my_achievements(self, user_id, client):
        """用户查看自己的成就进度"""
        resp = await client.get(f"/api/v1/rpg/achievements/my?user_id={user_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "achievements" in data

    @pytest.mark.asyncio
    async def test_badges(self, user_id, client):
        """用户徽章"""
        resp = await client.get(f"/api/v1/rpg/achievements/badges?user_id={user_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "badges" in data

    @pytest.mark.asyncio
    async def test_track_progress(self, user_id, client):
        """追踪进度"""
        resp = await client.post("/api/v1/rpg/achievements/track", json={
            "user_id": user_id, "type": "counter", "code": "", "value": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tracked"] is True

    @pytest.mark.asyncio
    async def test_check_unlock(self, user_id, client):
        """批量检查解锁"""
        resp = await client.post("/api/v1/rpg/achievements/check", json={
            "user_id": user_id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["checked"] is True


class TestCulturalEvents:
    """文化活动系统集成测试"""

    @pytest.mark.asyncio
    async def test_list_events(self, client):
        """列出所有活动"""
        resp = await client.get("/api/v1/rpg/events")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert data["count"] >= 5, f"期望至少 5 个种子活动, 实际 {data['count']}"

    @pytest.mark.asyncio
    async def test_list_by_type(self, client):
        """按类型筛选"""
        resp = await client.get("/api/v1/rpg/events?event_type=festival")
        assert resp.status_code == 200
        data = resp.json()
        for e in data["events"]:
            assert e["event_type"] == "festival"

    @pytest.mark.asyncio
    async def test_event_detail(self, client):
        """活动详情"""
        resp = await client.get("/api/v1/rpg/events/spring_festival")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "spring_festival"
        assert data["emoji"] == "🧧"
        assert len(data["tasks"]) == 4

    @pytest.mark.asyncio
    async def test_event_not_found(self, client):
        """不存在的活动"""
        resp = await client.get("/api/v1/rpg/events/nonexistent_event")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_join_event(self, user_id, client):
        """参与活动"""
        resp = await client.post("/api/v1/rpg/events/join", json={
            "user_id": user_id, "code": "spring_festival",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["joined"] is True
        assert data["event_code"] == "spring_festival"

    @pytest.mark.asyncio
    async def test_join_duplicate(self, user_id, client):
        """重复参与"""
        # 先参与
        await client.post("/api/v1/rpg/events/join", json={
            "user_id": user_id, "code": "spring_festival",
        })
        # 重复
        resp = await client.post("/api/v1/rpg/events/join", json={
            "user_id": user_id, "code": "spring_festival",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_submit_progress(self, user_id, client):
        """提交活动进度"""
        # 先参与
        await client.post("/api/v1/rpg/events/join", json={
            "user_id": user_id, "code": "spring_festival",
        })
        # 提交进度
        resp = await client.post("/api/v1/rpg/events/progress", json={
            "user_id": user_id, "code": "spring_festival",
            "task_index": 0, "value": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "task_completed" in data

    @pytest.mark.asyncio
    async def test_my_events(self, user_id, client):
        """我的活动列表"""
        # 先参与一个活动
        await client.post("/api/v1/rpg/events/join", json={
            "user_id": user_id, "code": "spring_festival",
        })
        resp = await client.get(f"/api/v1/rpg/events/my?user_id={user_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert data["count"] > 0, "应该已经有参与的活动"


class TestArchitectAgent:
    """总架构师集成测试"""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """系统健康检查"""
        resp = await client.get("/api/v1/rpg/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert "checks" in data
        assert "database" in data["checks"]

    @pytest.mark.asyncio
    async def test_dashboard(self, client):
        """数据面板"""
        resp = await client.get("/api/v1/rpg/system/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_code_audit(self, client):
        """代码审查"""
        resp = await client.get("/api/v1/rpg/system/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert "todos" in data
        assert "agent_route_gaps" in data
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_full_report(self, client):
        """完整巡检报告"""
        resp = await client.get("/api/v1/rpg/system/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "markdown" in data
        assert len(data["markdown"]) > 100, "报告不应为空"
