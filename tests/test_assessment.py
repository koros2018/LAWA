"""
集成测试：评估路由 — DB 持久化端点
"""
import pytest
import uuid
from sqlalchemy import select
from src.models.assessment import Assessment, AssessmentQuestion


@pytest.mark.asyncio
async def test_get_assessment_not_found(client):
    """查询不存在的评估返回404"""
    resp = await client.get(f"/api/v1/assessment/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_assessment_invalid_uuid(client):
    """无效UUID返回400"""
    resp = await client.get("/api/v1/assessment/not-a-uuid")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_assessment_with_questions(client, db_session):
    """查询带题目的评估"""
    # 创建用户
    uid = uuid.uuid4()
    from src.models.user import User
    user = User(id=uid, username="atest", email="atest@t.com", password_hash="h")
    db_session.add(user)
    await db_session.flush()

    # 创建评估
    aid = uuid.uuid4()
    a = Assessment(
        id=aid, user_id=uid, lang="en",
        overall_level="B1", status="completed",
        dimension_scores={"grammar": {"level": "B1", "score": 72}},
        summary="Good progress",
    )
    db_session.add(a)

    # 添加题目
    q1 = AssessmentQuestion(
        assessment_id=aid, dimension="grammar", difficulty="medium",
        question_type="multiple_choice", question_text="What is X?",
        order_index=1,
    )
    q2 = AssessmentQuestion(
        assessment_id=aid, dimension="vocabulary", difficulty="easy",
        question_type="fill_blank", question_text="The opposite of big is __",
        order_index=2,
    )
    db_session.add_all([q1, q2])
    await db_session.flush()

    resp = await client.get(f"/api/v1/assessment/{aid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(aid)
    assert data["lang"] == "en"
    assert data["overall_level"] == "B1"
    assert data["summary"] == "Good progress"
    assert len(data["questions"]) == 2
    assert data["questions"][0]["dimension"] == "grammar"
    assert data["questions"][1]["dimension"] == "vocabulary"


@pytest.mark.asyncio
async def test_get_assessment_history_empty(client, db_session):
    """无评估记录时返回空列表"""
    uid = uuid.uuid4()
    resp = await client.get(f"/api/v1/assessment/history/{uid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["assessments"] == []


@pytest.mark.asyncio
async def test_get_assessment_history_with_data(client, db_session):
    """有评估记录时正确返回"""
    uid = uuid.uuid4()
    from src.models.user import User
    user = User(id=uid, username="hist", email="hist@t.com", password_hash="h")
    db_session.add(user)
    await db_session.flush()

    a1 = Assessment(id=uuid.uuid4(), user_id=uid, lang="en", overall_level="A2", status="completed")
    a2 = Assessment(id=uuid.uuid4(), user_id=uid, lang="zh", overall_level="HSK3", status="completed")
    db_session.add_all([a1, a2])
    await db_session.flush()

    resp = await client.get(f"/api/v1/assessment/history/{uid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["assessments"]) == 2


@pytest.mark.asyncio
async def test_get_assessment_history_invalid_uuid(client):
    """无效UUID返回400"""
    resp = await client.get("/api/v1/assessment/history/bad-id")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_assessment_history_pagination(client, db_session):
    """分页参数正确工作"""
    uid = uuid.uuid4()
    from src.models.user import User
    user = User(id=uid, username="pag", email="pag@t.com", password_hash="h")
    db_session.add(user)
    await db_session.flush()

    for i in range(5):
        a = Assessment(id=uuid.uuid4(), user_id=uid, lang="en", overall_level="A1", status="completed")
        db_session.add(a)
    await db_session.flush()

    # 取前2条
    resp = await client.get(f"/api/v1/assessment/history/{uid}?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["assessments"]) == 2
    assert data["offset"] == 0
    assert data["limit"] == 2

    # 跳过前2条
    resp = await client.get(f"/api/v1/assessment/history/{uid}?limit=5&offset=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["assessments"]) == 3
