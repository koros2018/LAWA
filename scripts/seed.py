#!/usr/bin/env python3
"""
LAWA 种子数据脚本
用于演示/试用场景，创建示例用户 + 评估记录 + 任务
用法：python scripts/seed.py
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DB_USE_SQLITE", "true")
os.environ.setdefault("SQLITE_PATH", "./data/lawa.db")
os.environ.setdefault("JWT_SECRET", "lawa-dev-secret")
os.environ.setdefault("LLM_NVIDIA_KEY", "")
os.environ.setdefault("LLM_OPENCODE_KEY", "")
os.environ.setdefault("LOG_LEVEL", "WARNING")

from src.database import engine, Base, AsyncSessionLocal
from src.models.user import User, LawaProfile
from src.models.assessment import Assessment, AssessmentQuestion
from src.models.coin import CoinTransaction
from src.models.companion import CompanionSession, CompanionMessage
from src.models.task import Task
from src.utils.security import hash_password


DEMO_USERS = [
    {"username": "alice", "password": "demo123", "email": "alice@lawa.dev", "native": "zh", "learn": "en", "coins": 2500, "level": "B1"},
    {"username": "bob", "password": "demo123", "email": "bob@lawa.dev", "native": "en", "learn": "zh", "coins": 1800, "level": "HSK2"},
    {"username": "carol", "password": "demo123", "email": "carol@lawa.dev", "native": "zh", "learn": "fr", "coins": 3200, "level": "A2"},
]

DEMO_TASKS = [
    {"title": "翻译：餐厅菜单中译英", "task_type": "translation", "language_pair": "zh->en", "difficulty": 2, "reward_coin": 50, "status": "open"},
    {"title": "润色：求职信英文版", "task_type": "proofreading", "language_pair": "en->en", "difficulty": 3, "reward_coin": 80, "status": "open"},
    {"title": "对话练习：酒店入住", "task_type": "speaking", "language_pair": "zh->en", "difficulty": 1, "reward_coin": 30, "status": "open"},
    {"title": "翻译：技术文档片段", "task_type": "translation", "language_pair": "en->zh", "difficulty": 4, "reward_coin": 120, "status": "open"},
    {"title": "摘要：英文新闻短篇", "task_type": "summary", "language_pair": "en->en", "difficulty": 2, "reward_coin": 60, "status": "open"},
]

DEMO_SCENARIOS_EN = [
    ("restaurant", "Order food at a restaurant", "You are a customer at an Italian restaurant. The waiter approaches you."),
    ("hotel", "Check into a hotel", "You arrive at a hotel for a 3-night stay. The receptionist greets you."),
    ("airport", "At the airport", "You are checking in for an international flight."),
]


async def seed():
    print("🌱 LAWA 种子数据生成中...")

    # 建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✅ 数据库表就绪")

    async with AsyncSessionLocal() as db:
        # 清除旧数据
        for table in reversed(Base.metadata.sorted_tables):
            await db.execute(table.delete())
        await db.flush()

        user_ids = {}

        # 创建演示用户
        for u in DEMO_USERS:
            uid = uuid.uuid4()
            user = User(
                id=uid,
                username=u["username"],
                email=u["email"],
                password_hash=hash_password(u["password"]),
            )
            db.add(user)

            profile = LawaProfile(
                user_id=uid,
                native_lang=u["native"],
                learn_lang=u["learn"],
                current_level=u["level"],
                total_coins=u["coins"],
                interests=["旅行", "音乐", "科技"],
                weak_areas=["写作", "口语"] if u["learn"] == "en" else ["汉字", "声调"],
                learning_style="visual" if u["username"] != "bob" else "auditory",
            )
            db.add(profile)

            # 注册奖励流水
            txn = CoinTransaction(
                user_id=uid,
                type="register",
                amount=1000,
                balance_before=0,
                balance_after=1000,
                description="注册奖励",
            )
            db.add(txn)

            # 额外金币
            if u["coins"] > 1000:
                extra = u["coins"] - 1000
                txn2 = CoinTransaction(
                    user_id=uid,
                    type="bonus",
                    amount=extra,
                    balance_before=1000,
                    balance_after=u["coins"],
                    description="演示账户额外金币",
                )
                db.add(txn2)

            user_ids[u["username"]] = uid
            print(f"  👤 {u['username']}: {u['native']}→{u['learn']} Lv.{u['level']} 🪙{u['coins']}")

        await db.flush()

        # 创建演示任务（alice 发布）
        publisher_id = user_ids["alice"]
        for t in DEMO_TASKS:
            task = Task(
                id=uuid.uuid4(),
                publisher_id=publisher_id,
                title=t["title"],
                task_type=t["task_type"],
                language_pair=t["language_pair"],
                difficulty=t["difficulty"],
                reward_coin=t["reward_coin"],
                status=t["status"],
            )
            db.add(task)
        print(f"  📋 {len(DEMO_TASKS)} 个演示任务")

        # 创建示例评估（alice）
        aid = uuid.uuid4()
        assessment = Assessment(
            id=aid,
            user_id=publisher_id,
            lang="en",
            status="completed",
            overall_level="B1",
            dimension_scores={
                "grammar": {"level": "B1", "score": 75},
                "vocabulary": {"level": "B2", "score": 82},
                "reading": {"level": "B1", "score": 70},
                "writing": {"level": "A2", "score": 58},
                "speaking": {"level": "B1", "score": 68},
            },
            summary="整体英语水平 B1，词汇表现亮眼（B2），写作需要加强。",
            strengths=["词汇量丰富", "语法基础扎实"],
            weaknesses=["写作结构", "时态一致性"],
            recommendations=["每天写日记练习写作", "使用连接的词语改善段落连贯性"],
        )
        db.add(assessment)

        # 添加评估题目
        for i, (dim, q_text) in enumerate([
            ("grammar", "Choose the correct form: She ___ to school every day."),
            ("vocabulary", 'What does "ubiquitous" mean?'),
            ("reading", "Read the passage and answer: What is the main idea?"),
            ("writing", "Write 3 sentences about your daily routine."),
            ("speaking", "Describe your favorite hobby in 30 seconds."),
        ]):
            q = AssessmentQuestion(
                assessment_id=aid,
                dimension=dim,
                difficulty=["easy", "medium", "medium", "hard", "medium"][i],
                question_type=["multiple_choice", "multiple_choice", "multiple_choice", "open_ended", "open_ended"][i],
                question_text=q_text,
                options=["A", "B", "C", "D"] if i < 3 else None,
                user_answer="Sample answer",
                is_correct=i < 3,
                score=8 if i < 3 else 6,
                order_index=i,
            )
            db.add(q)
        print(f"  📊 1 份示例评估 + 5 道题")

        # Carol 给 bob 做了伴读会话
        carol_id = user_ids["carol"]
        bob_id = user_ids["bob"]
        sid = uuid.uuid4()
        session = CompanionSession(
            id=sid,
            user_id=bob_id,
            lang="zh",
            scenario_id="restaurant",
            status="in_progress",
        )
        db.add(session)

        msg1 = CompanionMessage(
            session_id=sid,
            role="assistant",
            content="欢迎来到中文练习！今天我们在餐厅场景练习。你好，请问几位？",
        )
        msg2 = CompanionMessage(
            session_id=sid,
            role="user",
            content="两位。有靠窗的位子吗？",
        )
        db.add_all([msg1, msg2])
        print(f"  💬 1 个伴读会话 (bob 学中文)")

        await db.flush()
        await db.commit()
        print(f"\n🎉 种子数据完成！")
        print(f"   演示账户: alice / bob / carol  密码: demo123")
        print(f"   API: http://localhost:6288")
        print(f"   前端: http://localhost:6289")
        print(f"   Swagger: http://localhost:6288/docs")


if __name__ == "__main__":
    asyncio.run(seed())
