"""
LAWA RPG 系统 API 路由

涵盖：角色系统 + 世界地图 + 任务/副本 + 公会 + 商店/装备 + 成就 + 总架构师 + 文化活动
共 49 端点，18 个 Agent
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.main import get_db
from pydantic import BaseModel, Field
from src.routes.auth import get_current_user
from src.models.user import User
from typing import Optional
from src.agent.character_agent import CharacterAgent, CHARACTER_CLASSES
from src.agent.quest_agent import QuestAgent

router = APIRouter(prefix="/api/v1/rpg", tags=["RPG"])
character_agent = CharacterAgent()
quest_agent = QuestAgent()


# ═══════════════════════════════════════
#  请求模型
# ═══════════════════════════════════════
class AddXPRequest(BaseModel):
    user_id: str
    source: str = "study_10min"
    amount: int = 5

class ChooseClassRequest(BaseModel):
    user_id: str
    class_key: str

class AllocateTalentRequest(BaseModel):
    user_id: str
    skill: str
    points: int = 1

class SetTitleRequest(BaseModel):
    user_id: str
    title: str

class AcceptQuestRequest(BaseModel):
    user_id: str
    quest_code: str

class SubmitQuestRequest(BaseModel):
    user_id: str
    quest_id: str
    progress: dict = {}

class QuestGenerateRequest(BaseModel):
    quest_code: Optional[str] = None
    lang: str = "en"
    skill_focus: str = "vocabulary"
    user_level: str = "B1"
    quest_type: str = "daily"

class TravelRequest(BaseModel):
    user_id: str
    target_zone_code: str


# ═══════════════════════════════════════
#  角色系统
# ═══════════════════════════════════════
@router.get("/character/classes")
async def list_classes():
    """列出所有可选职业"""
    return {"classes": CHARACTER_CLASSES}

@router.get("/character/{user_id}")
async def get_character(user_id: str):
    """获取角色面板"""
    result = await character_agent.run({"action": "get_profile", "user_id": user_id})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result

@router.get("/character/{user_id}/xp")
async def get_xp(user_id: str):
    """获取经验值信息"""
    result = await character_agent.run({"action": "get_xp", "user_id": user_id})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result

@router.get("/character/{user_id}/stats")
async def get_stats(user_id: str):
    """获取角色统计"""
    result = await character_agent.run({"action": "get_stats", "user_id": user_id})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result

@router.post("/character/xp")
async def add_xp(req: AddXPRequest):
    """增加经验值（自动处理升级）"""
    result = await character_agent.run({
        "action": "add_xp",
        "user_id": req.user_id,
        "source": req.source,
        "amount": req.amount,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/character/class")
async def choose_class(req: ChooseClassRequest):
    """选择职业"""
    result = await character_agent.run({
        "action": "choose_class",
        "user_id": req.user_id,
        "class_key": req.class_key,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/character/talent")
async def allocate_talent(req: AllocateTalentRequest):
    """分配天赋点"""
    result = await character_agent.run({
        "action": "allocate_talent",
        "user_id": req.user_id,
        "skill": req.skill,
        "points": req.points,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/character/title")
async def set_title(req: SetTitleRequest):
    """设置称号"""
    result = await character_agent.run({
        "action": "set_title",
        "user_id": req.user_id,
        "title": req.title,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════
#  世界地图
# ═══════════════════════════════════════
from src.database.main import get_db
from src.models.world import LanguageZone, ZoneNode, ZoneConnection
from sqlalchemy import select

@router.get("/world/zones")
async def list_zones(db: AsyncSession = Depends(get_db)):
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

@router.get("/world/zones/{zone_code}")
async def get_zone(zone_code: str, db: AsyncSession = Depends(get_db)):
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

@router.get("/world/nodes")
async def list_nodes(zone_code: Optional[str] = None, db: AsyncSession = Depends(get_db)):
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


# ═══════════════════════════════════════
#  任务系统
# ═══════════════════════════════════════
@router.get("/quests/available")
async def list_available_quests(
    user_id: str,
    quest_type: Optional[str] = None,
    zone_code: Optional[str] = None,
    cefr_level: Optional[str] = None,
):
    """列出可用任务模板"""
    result = await quest_agent.run({
        "action": "list_available",
        "user_id": user_id,
        "quest_type": quest_type,
        "skill_focus": cefr_level,  # map cefr to skill filter
        "zone_code": zone_code,
    })
    return result

@router.get("/quests/daily")
async def get_daily_quests(user_id: str):
    """获取今日日常任务"""
    result = await quest_agent.run({
        "action": "get_daily",
        "user_id": user_id,
    })
    return result

@router.get("/quests/active")
async def get_active_quests(user_id: str):
    """获取当前进行中的任务"""
    result = await quest_agent.run({
        "action": "get_active",
        "user_id": user_id,
    })
    return result

@router.post("/quests/accept")
async def accept_quest(req: AcceptQuestRequest):
    """接取任务"""
    result = await quest_agent.run({
        "action": "accept",
        "user_id": req.user_id,
        "quest_code": req.quest_code,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/quests/submit")
async def submit_quest(req: SubmitQuestRequest):
    """提交任务进度"""
    result = await quest_agent.run({
        "action": "submit",
        "user_id": req.user_id,
        "user_quest_id": req.quest_id,
        "progress": req.progress,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/quests/{quest_id}/complete")
async def complete_quest(quest_id: str, user_id: str):
    """完成任务"""
    result = await quest_agent.run({
        "action": "complete",
        "user_id": user_id,
        "user_quest_id": quest_id,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/quests/generate-content")
async def generate_quest_content(req: QuestGenerateRequest):
    """LLM 动态生成任务内容（题目/阅读材料/对话框/文化注解）"""
    result = await quest_agent.run({
        "action": "generate_content",
        "quest_code": req.quest_code,
        "lang": req.lang,
        "skill_focus": req.skill_focus,
        "user_level": req.user_level,
        "quest_type": req.quest_type,
    })
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result


@router.post("/quests/generate-daily")
async def generate_daily_quest_endpoint(req: QuestGenerateRequest):
    """LLM 动态生成一个完整每日任务并写入DB"""
    result = await quest_agent.run({
        "action": "generate_daily_quest",
        "lang": req.lang,
        "skill_focus": req.skill_focus,
        "user_level": req.user_level,
    })
    if "error" in result:
        raise HTTPException(500, result["error"])
    return result


# ═══════════════════════════════════════
#  区域旅行
# ═══════════════════════════════════════
@router.post("/world/travel")
async def travel_to_zone(req: TravelRequest, db: AsyncSession = Depends(get_db)):
        # 查找目标区域
        result = await db.execute(
            select(LanguageZone).where(LanguageZone.code == req.target_zone_code)
        )
        target = result.scalar_one_or_none()
        if not target:
            raise HTTPException(404, f"区域不存在: {req.target_zone_code}")

        # 检查用户当前区域
        from src.models.user import LawaProfile
        profile_result = await db.execute(
            select(LawaProfile).where(LawaProfile.user_id == req.user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(404, "用户画像不存在")

        # 更新当前位置
        profile.current_zone_id = target.id
        profile.home_zone = target.code  # 保留兼容
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


# ═══════════════════════════════════════
#  公会系统
# ═══════════════════════════════════════
from src.agent.guild_agent import GuildAgent

guild_agent = GuildAgent()


class CreateGuildRequest(BaseModel):
    user_id: str
    name: str
    language: str = "en"
    description: str = ""
    emblem: str = "🛡️"

class JoinGuildRequest(BaseModel):
    user_id: str
    guild_id: str

class ContributeRequest(BaseModel):
    user_id: str
    amount: int = 10
    source: str = "study"

class TaskProgressRequest(BaseModel):
    guild_id: str
    task_id: str
    value: int = 1


@router.get("/guilds")
async def list_guilds(language: str = "en", name: str = ""):
    result = await guild_agent.run({"action": "list", "language": language, "name": name})
    return result

@router.get("/guild/my")
async def my_guild(current_user: User = Depends(get_current_user)):
    result = await guild_agent.run({"action": "my_guild", "user_id": str(current_user.id)})
    return result

@router.get("/guild/{guild_id}")
async def guild_detail(guild_id: str):
    result = await guild_agent.run({"action": "detail", "guild_id": guild_id})
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result

@router.post("/guild/create")
async def create_guild(req: CreateGuildRequest, current_user: User = Depends(get_current_user)):
    result = await guild_agent.run({
        "action": "create",
        "user_id": str(current_user.id),
        "name": req.name,
        "language": req.language,
        "description": req.description,
        "emblem": req.emblem,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/guild/join")
async def join_guild(req: JoinGuildRequest):
    result = await guild_agent.run({"action": "join", "user_id": req.user_id, "guild_id": req.guild_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/guild/leave")
async def leave_guild(current_user: User = Depends(get_current_user), guild_id: str = ""):
    result = await guild_agent.run({"action": "leave", "user_id": str(current_user.id), "guild_id": guild_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/guild/contribute")
async def contribute(req: ContributeRequest):
    result = await guild_agent.run({
        "action": "contribute",
        "user_id": req.user_id,
        "amount": req.amount,
        "source": req.source,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.get("/guild/{guild_id}/tasks")
async def guild_tasks(guild_id: str):
    result = await guild_agent.run({"action": "tasks", "guild_id": guild_id})
    return result

@router.post("/guild/tasks/progress")
async def guild_task_progress(req: TaskProgressRequest):
    result = await guild_agent.run({
        "action": "task_progress",
        "guild_id": req.guild_id,
        "task_id": req.task_id,
        "value": req.value,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════
#  道具商店
# ═══════════════════════════════════════
from src.agent.item_agent import ItemAgent

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


@router.get("/shop")
async def shop(category: str = "all"):
    return await item_agent.run({"action": "shop", "category": category})

@router.get("/inventory")
async def inventory(user_id: str):
    return await item_agent.run({"action": "inventory", "user_id": user_id})

@router.get("/equipped")
async def equipped(user_id: str):
    return await item_agent.run({"action": "equipped", "user_id": user_id})

@router.post("/shop/buy")
async def buy(req: BuyRequest):
    result = await item_agent.run({
        "action": "buy", "user_id": req.user_id, "item_type": req.item_type,
        "item_id": req.item_id, "quantity": req.quantity,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/inventory/equip")
async def equip(req: EquipRequest):
    result = await item_agent.run({"action": "equip", "user_id": req.user_id, "inv_id": req.inv_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.post("/inventory/use")
async def use_item(req: UseRequest):
    result = await item_agent.run({"action": "use", "user_id": req.user_id, "inv_id": req.inv_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

@router.get("/craft/recipes")
async def craft_recipes():
    return await item_agent.run({"action": "recipes"})

@router.post("/craft")
async def craft(req: CraftRequest):
    result = await item_agent.run({"action": "craft", "user_id": req.user_id, "recipe_id": req.recipe_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════
#  成就系统
# ═══════════════════════════════════════
from src.agent.achievement_agent import AchievementAgent

achievement_agent = AchievementAgent()


class TrackProgressRequest(BaseModel):
    user_id: str
    type: str = "counter"
    code: str = ""
    value: int = 1


class CheckUnlockRequest(BaseModel):
    user_id: str


@router.get("/achievements")
async def list_achievements(category: str = "all"):
    return await achievement_agent.run({"action": "list", "category": category})


@router.get("/achievements/my")
async def my_achievements(user_id: str):
    return await achievement_agent.run({"action": "my", "user_id": user_id})


@router.post("/achievements/track")
async def track_progress(req: TrackProgressRequest):
    result = await achievement_agent.run({
        "action": "track", "user_id": req.user_id,
        "type": req.type, "code": req.code, "value": req.value,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/achievements/badges")
async def my_badges(user_id: str):
    return await achievement_agent.run({"action": "badges", "user_id": user_id})


@router.post("/achievements/check")
async def check_unlock(req: CheckUnlockRequest):
    result = await achievement_agent.run({"action": "check_unlock", "user_id": req.user_id})
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════
#  总架构师（系统监督）
# ═══════════════════════════════════════
from src.agent.architect_agent import ArchitectAgent

architect_agent = ArchitectAgent()


@router.get("/system/health")
async def system_health():
    """系统健康检查 —— DB连接/表完整性/Agent清单/行数统计"""
    return await architect_agent.run({"action": "health"})


@router.get("/system/dashboard")
async def system_dashboard():
    """数据面板 —— 各子系统聚合统计"""
    return await architect_agent.run({"action": "dashboard"})


@router.get("/system/audit")
async def system_audit():
    """代码审查 —— TODO扫描/Agent路由缺口/潜在问题"""
    return await architect_agent.run({"action": "audit"})


@router.get("/system/report")
async def system_report():
    """完整巡检报告 —— Markdown格式"""
    return await architect_agent.run({"action": "report"})


# ═══════════════════════════════════════
#  文化节日 & 限时活动
# ═══════════════════════════════════════
from src.agent.event_agent import EventAgent

event_agent = EventAgent()


class JoinEventRequest(BaseModel):
    user_id: str
    code: str


class EventProgressRequest(BaseModel):
    user_id: str
    code: str
    task_index: int = 0
    value: int = 1


@router.get("/events")
async def list_events(
    event_type: str = "all",
    zone_code: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """活动列表 —— 支持按类型/区域/用户筛选"""
    return await event_agent.run({
        "action": "list", "event_type": event_type,
        "zone_code": zone_code, "user_id": user_id,
    })


@router.get("/events/my")
async def my_events(user_id: str):
    """我的活动列表 —— 必须在 /{event_code} 之前！"""
    return await event_agent.run({"action": "my", "user_id": user_id})


@router.post("/events/join")
async def join_event(req: JoinEventRequest):
    """参与活动"""
    result = await event_agent.run({
        "action": "join", "user_id": req.user_id, "code": req.code,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/events/progress")
async def event_progress(req: EventProgressRequest):
    """提交活动进度"""
    result = await event_agent.run({
        "action": "progress", "user_id": req.user_id,
        "code": req.code, "task_index": req.task_index, "value": req.value,
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/events/{event_code}")
async def event_detail(event_code: str, user_id: Optional[str] = None):
    """活动详情 —— 含用户参与状态（兜底路由，必须放最后）"""
    return await event_agent.run({
        "action": "detail", "code": event_code, "user_id": user_id,
    })


# ── LLM 驱动：活动生成 ──

class EventGenerateRequest(BaseModel):
    lang: str = Field(default="en", description="语言")
    event_type: str = Field(default="festival", description="活动类型")
    user_level: Optional[str] = Field(default=None, description="用户等级")
    zone_code: Optional[str] = Field(default=None, description="区域代码")


@router.post("/events/generate")
async def generate_event(req: EventGenerateRequest):
    """LLM 生成完整文化活动"""
    result = await event_agent.run({
        "action": "generate_event",
        "lang": req.lang,
        "event_type": req.event_type,
        "user_level": req.user_level or ("B1" if req.lang == "en" else "HSK3"),
        "zone_code": req.zone_code or ("en" if req.lang == "en" else "cn"),
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


class EventContentRequest(BaseModel):
    event_code: str = Field(..., description="活动代码")
    lang: str = Field(default="en", description="语言")
    user_level: Optional[str] = Field(default=None, description="用户等级")


@router.post("/events/generate-content")
async def generate_event_content(req: EventContentRequest):
    """LLM 为已有活动生成/增强任务内容"""
    result = await event_agent.run({
        "action": "generate_event_content",
        "event_code": req.event_code,
        "lang": req.lang,
        "user_level": req.user_level or ("B1" if req.lang == "en" else "HSK3"),
    })
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
