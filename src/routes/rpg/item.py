"""道具商店 & 装备系统路由"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from src.agent.item_agent import ItemAgent
from src.routes.auth import get_current_user
from src.models.user import User
from typing import Optional

item_agent = ItemAgent()

# 商店路由
shop_router = APIRouter(prefix="/shop", tags=["RPG-Item"])
# 背包路由（独立于 /shop）
inventory_router = APIRouter(prefix="/inventory", tags=["RPG-Item"])


class BuyRequest(BaseModel):
    user_id: str
    item_type: str
    item_id: str
    quantity: int = 1


class EquipRequest(BaseModel):
    user_id: str
    inv_id: str


class UseRequest(BaseModel):
    user_id: str
    inv_id: str


class CraftRequest(BaseModel):
    user_id: str
    recipe_id: str


@shop_router.get("")
async def shop(category: str = "all"):
    """商店列表"""
    return await item_agent.run({"action": "shop", "category": category})


@shop_router.post("/buy")
async def buy(req: BuyRequest):
    """购买道具"""
    result = await item_agent.run({
        "action": "buy", "user_id": req.user_id, "item_type": req.item_type,
        "item_id": req.item_id, "quantity": req.quantity,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@inventory_router.get("")
async def inventory(user_id: Optional[str] = Query(None), current_user: User = Depends(get_current_user)):
    """背包"""
    uid = user_id or str(current_user.id)
    return await item_agent.run({"action": "inventory", "user_id": uid})


@inventory_router.get("/equipped")
async def equipped(user_id: Optional[str] = Query(None), current_user: User = Depends(get_current_user)):
    """已装备"""
    uid = user_id or str(current_user.id)
    return await item_agent.run({"action": "equipped", "user_id": uid})


@inventory_router.post("/equip")
async def equip(req: EquipRequest):
    """装备道具"""
    result = await item_agent.run({"action": "equip", "user_id": req.user_id, "inv_id": req.inv_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@inventory_router.post("/use")
async def use_item(req: UseRequest):
    """使用道具"""
    result = await item_agent.run({"action": "use", "user_id": req.user_id, "inv_id": req.inv_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@shop_router.get("/craft/recipes")
async def craft_recipes():
    """合成配方列表"""
    return await item_agent.run({"action": "recipes"})


@shop_router.post("/craft")
async def craft(req: CraftRequest):
    """合成"""
    result = await item_agent.run({"action": "craft", "user_id": req.user_id, "recipe_id": req.recipe_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result