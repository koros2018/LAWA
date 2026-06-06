"""世界地图 & 区域旅行路由"""
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.models.world import LanguageZone, ZoneNode, ZoneConnection
from sqlalchemy import select
from src.models.user import LawaProfile
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/world", tags=["RPG-World"])


class TravelRequest(BaseModel):
    user_id: str
    target_zone_code: str


@router.get("/zones")
async def list_zones(db: AsyncSession = Depends(get_db)):
    """列出所有语言区域"""
    result = await db.execute(select(LanguageZone))
    zones = result.scalars().all()
    return {
        "zones": [
            {
                "id": str(z.id),
                "code": z.code,
                "name": z.name,
                "culture_theme": z.culture_theme,
                "native_lang": z.native_lang,
                "map_position": z.map_position,
            }
            for z in zones
        ]
    }


@router.get("/zones/{zone_code}")
async def get_zone(zone_code: str, db: AsyncSession = Depends(get_db)):
    """获取区域详情（含所有节点）"""
    result = await db.execute(
        select(LanguageZone).where(LanguageZone.code == zone_code)
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(404, f"区域不存在: {zone_code}")

    nodes_result = await db.execute(
        select(ZoneNode).where(ZoneNode.zone_id == zone.id)
    )
    nodes = nodes_result.scalars().all()

    return {
        "zone": {
            "id": str(zone.id),
            "code": zone.code,
            "name": zone.name,
            "culture_theme": zone.culture_theme,
            "native_lang": zone.native_lang,
            "map_position": zone.map_position,
        },
        "nodes": [
            {
                "id": str(n.id),
                "code": n.code,
                "name": n.name,
                "node_type": n.node_type,
                "skill_focus": n.skill_focus,
                "cefr_min": n.cefr_min,
                "cefr_max": n.cefr_max,
                "daily_quest_pool": n.daily_quest_pool or [],
                "npc_dialogue": n.npc_dialogue or {},
                "description": n.description or "",
            }
            for n in nodes
        ]
    }


@router.get("/nodes")
async def list_nodes(zone_code: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """列出场景节点（支持按区域筛选）"""
    query = select(ZoneNode)
    if zone_code:
        zone_result = await db.execute(
            select(LanguageZone.id).where(LanguageZone.code == zone_code)
        )
        zone_id = zone_result.scalar_one_or_none()
        if not zone_id:
            raise HTTPException(404, f"区域不存在: {zone_code}")
        query = query.where(ZoneNode.zone_id == zone_id)

    result = await db.execute(query)
    nodes = result.scalars().all()
    return {
        "nodes": [
            {
                "id": str(n.id),
                "code": n.code,
                "name": n.name,
                "node_type": n.node_type,
                "skill_focus": n.skill_focus,
                "cefr_min": n.cefr_min,
                "cefr_max": n.cefr_max,
                "daily_quest_pool": n.daily_quest_pool or [],
                "npc_dialogue": n.npc_dialogue or {},
                "description": n.description or "",
            }
            for n in nodes
        ]
    }


@router.post("/travel")
async def travel_to_zone(req: TravelRequest, db: AsyncSession = Depends(get_db)):
    """跨区域旅行"""
    result = await db.execute(
        select(LanguageZone).where(LanguageZone.code == req.target_zone_code)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, f"区域不存在: {req.target_zone_code}")

    profile_result = await db.execute(
        select(LawaProfile).where(LawaProfile.user_id == req.user_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "用户画像不存在")

    profile.current_zone_id = target.id
    profile.home_zone = target.code
    await db.commit()

    return {
        "status": "ok",
        "message": f"已抵达 {target.name}",
        "zone": {
            "id": str(target.id),
            "code": target.code,
            "name": target.name,
            "culture_theme": target.culture_theme,
        }
    }
