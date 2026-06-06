"""
ItemAgent —— 道具与装备系统

管理：商店/背包/购买/装备/使用/合成
"""
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_
from src.database import AsyncSessionLocal
from src.database.session import get_async_session
from src.database.session import get_async_session
from src.models.equipment import (
    Equipment, Consumable, UserInventory, CraftRecipe, RARITY_CONFIG,
)
from src.models.user import LawaProfile
from src.models.coin import CoinTransaction
from src.agent.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ItemAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="ItemAgent")

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "")
        handlers = {
            "shop": self.shop,
            "inventory": self.inventory,
            "buy": self.buy,
            "equip": self.equip,
            "use": self.use_consumable,
            "recipes": self.recipes,
            "craft": self.craft,
            "equipped": self.equipped,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        try:
            result = await handler(payload)
            self.log_execution(payload, result)
            return result
        except Exception as e:
            logger.error(f"ItemAgent error: {e}")
            return {"error": str(e)}

    # ── 商店 ──

    async def shop(self, payload: dict) -> dict:
        """列出商店可购买物品"""
        category = payload.get("category", "all")  # all/equipment/consumable
        async with get_async_session() as session:
            items = []

            if category in ("all", "equipment"):
                eq_result = await session.execute(select(Equipment))
                for e in eq_result.scalars().all():
                    rarity_cfg = RARITY_CONFIG.get(e.rarity, RARITY_CONFIG["common"])
                    items.append({
                        "id": str(e.id), "code": e.code, "type": "equipment",
                        "name": e.name, "emoji": e.emoji, "description": e.description,
                        "slot": e.slot, "rarity": e.rarity, "rarity_color": rarity_cfg["color"],
                        "price_coin": e.price_coin, "price_guild_contrib": e.price_guild_contrib,
                        "effects": e.effects, "required_level": e.required_level,
                    })

            if category in ("all", "consumable"):
                co_result = await session.execute(select(Consumable))
                for c in co_result.scalars().all():
                    items.append({
                        "id": str(c.id), "code": c.code, "type": "consumable",
                        "name": c.name, "emoji": c.emoji, "description": c.description,
                        "rarity": "common", "rarity_color": "#9ca3af",
                        "price_coin": c.price_coin,
                        "effect_type": c.effect_type, "effect_value": c.effect_value,
                        "effect_duration_min": c.effect_duration_min,
                    })

            return {"items": items, "count": len(items)}

    # ── 背包 ──

    async def inventory(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        async with get_async_session() as session:
            result = await session.execute(
                select(UserInventory).where(UserInventory.user_id == user_id)
                .order_by(UserInventory.equipped.desc(), UserInventory.acquired_at.desc())
            )
            inv = result.scalars().all()

            items = []
            for i in inv:
                item_info = None
                if i.item_type == "equipment":
                    eq = await session.get(Equipment, i.item_id)
                    if eq:
                        item_info = {"name": eq.name, "emoji": eq.emoji, "slot": eq.slot,
                                     "rarity": eq.rarity, "effects": eq.effects}
                elif i.item_type == "consumable":
                    co = await session.get(Consumable, i.item_id)
                    if co:
                        item_info = {"name": co.name, "emoji": co.emoji,
                                     "effect_type": co.effect_type, "effect_value": co.effect_value}

                items.append({
                    "inv_id": str(i.id),
                    "item_type": i.item_type,
                    "item_id": i.item_id,
                    "quantity": i.quantity,
                    "equipped": bool(i.equipped),
                    "active_until": i.active_until.isoformat() if i.active_until else None,
                    "info": item_info,
                })

            return {"items": items, "count": len(items), "user_id": user_id}

    # ── 已装备 ──

    async def equipped(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        async with get_async_session() as session:
            result = await session.execute(
                select(UserInventory).where(
                    and_(UserInventory.user_id == user_id, UserInventory.equipped == 1)
                )
            )
            equipped = result.scalars().all()

            slots = {}
            active_buffs = {"xp_bonus_pct": 0, "coin_bonus_pct": 0, "correct_bonus_pct": 0}
            for i in equipped:
                eq = None
                if i.item_type == "equipment":
                    eq = await session.get(Equipment, i.item_id)
                elif i.item_type == "consumable" and i.active_until and i.active_until > datetime.now(timezone.utc):
                    co = await session.get(Consumable, i.item_id)
                    if co:
                        key = f"consumable_{co.effect_type}"
                        active_buffs[key] = active_buffs.get(key, 0) + co.effect_value

                if eq:
                    slots[eq.slot] = {"name": eq.name, "emoji": eq.emoji, "effects": eq.effects}
                    for k, v in (eq.effects or {}).items():
                        active_buffs[k] = active_buffs.get(k, 0) + v

            return {"slots": slots, "active_buffs": active_buffs, "user_id": user_id}

    # ── 购买 ──

    async def buy(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        item_type = payload["item_type"]  # equipment/consumable
        item_id = payload["item_id"]
        quantity = payload.get("quantity", 1)

        async with get_async_session() as session:
            profile = await self._get_profile(session, user_id)
            if not profile:
                return {"error": "用户画像不存在"}

            # 获取物品信息
            item = None
            if item_type == "equipment":
                item = await session.get(Equipment, item_id)
            elif item_type == "consumable":
                item = await session.get(Consumable, item_id)

            if not item:
                return {"error": "物品不存在"}

            cost = item.price_coin * quantity
            if profile.total_coins < cost:
                return {"error": f"金币不足: 需要 {cost}🪙, 余额 {profile.total_coins}🪙"}

            # 扣款
            profile.total_coins -= cost

            # 加入背包
            inv = UserInventory(
                user_id=user_id,
                item_type=item_type,
                item_id=item_id,
                quantity=quantity,
            )
            session.add(inv)
            await session.commit()
            await session.refresh(inv)

            logger.info(f"🛒 购买: user={user_id} {item_type}={item.code} x{quantity} for {cost}🪙")
            return {
                "status": "ok",
                "item_name": item.name,
                "quantity": quantity,
                "cost": cost,
                "balance": profile.total_coins,
            }

    # ── 装备 ──

    async def equip(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        inv_id = payload["inv_id"]

        async with get_async_session() as session:
            inv = await session.get(UserInventory, inv_id)
            if not inv or inv.user_id != user_id:
                return {"error": "物品不在背包中"}
            if inv.item_type != "equipment":
                return {"error": "只能装备equipment类型物品"}

            eq = await session.get(Equipment, inv.item_id)
            if not eq:
                return {"error": "装备模板不存在"}

            # 卸下同槽位的旧装备
            old_result = await session.execute(
                select(UserInventory).where(
                    and_(UserInventory.user_id == user_id, UserInventory.equipped == 1)
                )
            )
            for old in old_result.scalars().all():
                if old.item_type == "equipment":
                    old_eq = await session.get(Equipment, old.item_id)
                    if old_eq and old_eq.slot == eq.slot:
                        old.equipped = 0

            # 装备新物品
            inv.equipped = 1
            await session.commit()

            logger.info(f"⚔️ 装备: user={user_id} {eq.name} (slot={eq.slot})")
            return {"status": "ok", "equipped": eq.name, "slot": eq.slot, "effects": eq.effects}

    # ── 使用消耗品 ──

    async def use_consumable(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        inv_id = payload["inv_id"]

        async with get_async_session() as session:
            inv = await session.get(UserInventory, inv_id)
            if not inv or inv.user_id != user_id:
                return {"error": "物品不在背包中"}
            if inv.item_type != "consumable":
                return {"error": "只能使用consumable类型物品"}
            if inv.quantity <= 0:
                return {"error": "物品已用完"}

            co = await session.get(Consumable, inv.item_id)
            if not co:
                return {"error": "消耗品模板不存在"}

            # 减少数量
            inv.quantity -= 1

            # 如果是持续效果，设置active_until
            if co.effect_duration_min > 0:
                active_until = datetime.now(timezone.utc) + timedelta(minutes=co.effect_duration_min)
                # 创建激活记录
                active_inv = UserInventory(
                    user_id=user_id,
                    item_type="consumable",
                    item_id=inv.item_id,
                    quantity=1,
                    equipped=1,
                    active_until=active_until,
                )
                session.add(active_inv)

            # 如果是立即生效的效果（如xp_boost）
            # 这里记入效果状态，实际由学习流程读取
            await session.commit()

            logger.info(f"🧪 使用: user={user_id} {co.name} (effect={co.effect_type})")
            return {
                "status": "ok",
                "item_name": co.name,
                "effect_type": co.effect_type,
                "effect_value": co.effect_value,
                "duration_min": co.effect_duration_min,
                "remaining": inv.quantity,
            }

    # ── 合成 ──

    async def recipes(self, payload: dict) -> dict:
        """列出合成配方"""
        async with get_async_session() as session:
            result = await session.execute(select(CraftRecipe))
            recipes = result.scalars().all()
            return {
                "recipes": [
                    {
                        "id": str(r.id), "name": r.name, "description": r.description,
                        "ingredients": r.ingredients, "gold_cost": r.gold_cost,
                    }
                    for r in recipes
                ]
            }

    async def craft(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        recipe_id = payload["recipe_id"]

        async with get_async_session() as session:
            recipe = await session.get(CraftRecipe, recipe_id)
            if not recipe:
                return {"error": "配方不存在"}

            profile = await self._get_profile(session, user_id)
            if not profile:
                return {"error": "用户画像不存在"}

            # 检查金币
            if profile.total_coins < recipe.gold_cost:
                return {"error": f"金币不足: {recipe.gold_cost}🪙"}

            # 检查材料（背包中是否有足够材料）
            for ing in recipe.ingredients:
                needed = ing["quantity"]
                inv_result = await session.execute(
                    select(UserInventory).where(
                        and_(UserInventory.user_id == user_id, UserInventory.item_id == ing["item_id"])
                    )
                )
                user_items = inv_result.scalars().all()
                total_qty = sum(i.quantity for i in user_items)
                if total_qty < needed:
                    return {"error": f"材料不足: {ing.get('name', ing['item_id'])} (需要{needed}个, 现有{total_qty}个)"}

            # 扣除材料
            for ing in recipe.ingredients:
                needed = ing["quantity"]
                inv_result = await session.execute(
                    select(UserInventory).where(
                        and_(UserInventory.user_id == user_id, UserInventory.item_id == ing["item_id"])
                    ).order_by(UserInventory.acquired_at.asc())
                )
                for iv in inv_result.scalars().all():
                    if needed <= 0:
                        break
                    deduct = min(needed, iv.quantity)
                    iv.quantity -= deduct
                    needed -= deduct

            # 扣除金币
            profile.total_coins -= recipe.gold_cost

            # 产出结果
            new_inv = UserInventory(
                user_id=user_id,
                item_type=recipe.result_item_type,
                item_id=recipe.result_item_id,
                quantity=1,
            )
            session.add(new_inv)
            await session.commit()

            logger.info(f"🔨 合成: user={user_id} recipe={recipe.name}")
            return {"status": "ok", "crafted": recipe.name}

    # ── helpers ──

    async def _get_profile(self, session, user_id):
        result = await session.execute(
            select(LawaProfile).where(LawaProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()
