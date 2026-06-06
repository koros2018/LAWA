"""
LAWA RPG 系统路由入口

将 8 个子系统路由合并为一个主 router，保持 /api/v1/rpg 前缀。
"""
from fastapi import APIRouter
from .character import router as character_router
from .world import router as world_router
from .quest import router as quest_router
from .guild import router as guild_router
from .item import router as item_router
from .achievement import router as achievement_router
from .system import router as system_router
from .event import router as event_router

router = APIRouter(prefix="/api/v1/rpg", tags=["RPG"])

router.include_router(character_router)
router.include_router(world_router)
router.include_router(quest_router)
router.include_router(guild_router)
router.include_router(item_router)
router.include_router(achievement_router)
router.include_router(system_router)
router.include_router(event_router)
