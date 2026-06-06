"""道具商店 & 装备系统路由"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.agent.item_agent import ItemAgent

router = APIRouter(prefix="/shop", tags=["RPG-Item"])
item_agent = ItemAgent()


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


@router.get("")
async def shop(category: str = "all"):
    """商店列表"""
    return await item_agent.run({"action": "shop", "category": category})


@router.get("/inventory")
async def inventory(user_id: str):
    """背包"""
    return await item_agent.run({"action": "inventory", "user_id": user_id})


@router.get("/equipped")
async def equipped(user_id: str):
    """已装备"""
    return await item_agent.run({"action": "equipped", "user_id": user_id})


@router.post("/buy")
async def buy(req: BuyRequest):
    """购买道具"""
    result = await item_agent.run({
        "action": "buy", "user_id": req.user_id, "item_type": req.item_type,
        "item_id": req.item_id, "quantity": req.quantity,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/inventory/equip")
async def equip(req: EquipRequest):
    """装备道具"""
    result = await item_agent.run({"action": "equip", "user_id": req.user_id, "inv_id": req.inv_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/inventory/use")
async def use_item(req: UseRequest):
    """使用道具"""
    result = await item_agent.run({"action": "use", "user_id": req.user_id, "inv_id": req.inv_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/craft/recipes")
async def craft_recipes():
    """合成配方列表"""
    return await item_agent.run({"action": "recipes"})


@router.post("/craft")
async def craft(req: CraftRequest):
    """合成"""
    result = await item_agent.run({"action": "craft", "user_id": req.user_id, "recipe_id": req.recipe_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result