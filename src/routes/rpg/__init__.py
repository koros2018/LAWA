"""RPG 路由聚合入口"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/rpg", tags=["RPG"])

from . import character, world, quest, guild, item, achievement, system, event

router.include_router(character.router)
router.include_router(world.router)
router.include_router(quest.router)
router.include_router(guild.router)
router.include_router(item.router)
router.include_router(achievement.router)
router.include_router(system.router)
router.include_router(event.router)
