"""
LAWA RPG 公会系统种子数据
"""
import asyncio
import logging
from src.database import AsyncSessionLocal
from src.models.guild import LanguageGuild, GuildMember, GuildTask

logger = logging.getLogger(__name__)


async def seed_guilds():
    """播种公会数据（幂等）"""
    logger.info("🏛️ 开始播种公会系统...")

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        existing = await session.execute(
            select(LanguageGuild).limit(1)
        )
        if existing.scalar_one_or_none():
            logger.info("  公会数据已存在，跳过")
            return {"status": "skipped", "reason": "already seeded"}

        # ── 获取用户 ──
        from sqlalchemy import text
        users_r = await session.execute(text("SELECT id, username FROM users LIMIT 3"))
        users = [(r[0], r[1]) for r in users_r]
        alice_id, bob_id, carol_id = users[0][0], users[1][0], users[2][0]

        # ── 创建3个种子公会 ──
        guilds = [
            LanguageGuild(
                name="竹林学社",
                description="华夏区第一学术公会，专注于汉语学习与文化传承",
                language="zh",
                level=2,
                xp=150,
                member_count=2,
                member_limit=15,
                buffs={"xp_bonus_pct": 2},
                emblem="🎋",
                owner_id=alice_id,
            ),
            LanguageGuild(
                name="The Oxford Circle",
                description="A guild for English learners who love literature and debate",
                language="en",
                level=3,
                xp=400,
                member_count=3,
                member_limit=20,
                buffs={"xp_bonus_pct": 5},
                emblem="📚",
                owner_id=bob_id,
            ),
            LanguageGuild(
                name="深夜学习局",
                description="夜猫子专属，凌晨出没的语言突击队",
                language="zh",
                level=1,
                xp=30,
                member_count=1,
                member_limit=10,
                emblem="🦉",
                owner_id=carol_id,
            ),
        ]
        for g in guilds:
            session.add(g)
        await session.flush()

        # ── 公会成员 ──
        members_data = [
            # 竹林学社 (guilds[0])
            (guilds[0].id, alice_id, "owner"),
            (guilds[0].id, carol_id, "member"),
            # The Oxford Circle (guilds[1])
            (guilds[1].id, bob_id, "owner"),
            (guilds[1].id, alice_id, "co_owner"),
            (guilds[1].id, carol_id, "member"),
            # 深夜学习局 (guilds[2])
            (guilds[2].id, carol_id, "owner"),
        ]
        for gid, uid, role in members_data:
            session.add(GuildMember(guild_id=gid, user_id=uid, role=role))

        # ── 公会任务 ──
        tasks_data = [
            {
                "guild_id": guilds[0].id,
                "name": "集体成语接龙",
                "description": "每人贡献5个成语，连续完成50次接龙",
                "target_value": 50,
                "current_value": 12,
                "xp_reward": 200,
                "coin_reward": 100,
            },
            {
                "guild_id": guilds[0].id,
                "name": "竹林天书·翻译挑战",
                "description": "协作翻译一篇古文（300字）",
                "target_value": 300,
                "current_value": 45,
                "xp_reward": 300,
                "coin_reward": 150,
            },
            {
                "guild_id": guilds[1].id,
                "name": "Shakespeare Circle",
                "description": "Read and discuss one Shakespeare sonnet per day for a week",
                "target_value": 7,
                "current_value": 3,
                "xp_reward": 250,
                "coin_reward": 120,
            },
            {
                "guild_id": guilds[1].id,
                "name": "Debate Championship",
                "description": "Prepare and hold a formal English debate (4 speakers)",
                "target_value": 4,
                "current_value": 0,
                "xp_reward": 400,
                "coin_reward": 200,
            },
            {
                "guild_id": guilds[2].id,
                "name": "凌晨听力马拉松",
                "description": "累计完成100分钟深夜听力练习",
                "target_value": 100,
                "current_value": 25,
                "xp_reward": 150,
                "coin_reward": 80,
            },
        ]
        for td in tasks_data:
            session.add(GuildTask(**td))

        await session.commit()

    logger.info(f"🎉 公会播种完成！3公会 6成员 5任务")
    return {
        "status": "ok",
        "guilds": 3,
        "members": 6,
        "tasks": 5,
    }


# CLI entry
if __name__ == "__main__":
    asyncio.run(seed_guilds())
