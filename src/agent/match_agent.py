"""
LAWA MatchAgent — 跨国语言匹配引擎

根据用户画像匹配语言学习伙伴：
- 可用语言 → 想学的语言
- 用户画像VARK匹配
- 等级对等推荐
"""
import uuid, random
from typing import Optional
from loguru import logger
from src.agent.base_agent import BaseAgent
from src.config import settings


class MatchAgent(BaseAgent):
    """匹配引擎Agent"""

    def __init__(self):
        super().__init__("MatchAgent")
        # { user_id: profile_dict }
        self._profiles: dict[str, dict] = {}

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "find_partners")
        handlers = {
            "register": self.register_profile,
            "find_partners": self.find_partners,
            "match": self.match_pair,
            "list_matches": self.list_matches,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"未知操作: {action}"}
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    # ── 注册/更新用户画像 ──
    async def register_profile(self, payload: dict) -> dict:
        profile = {
            "user_id": payload["user_id"],
            "native_language": payload.get("native_language", "zh-CN"),
            "target_language": payload.get("target_language", "en"),
            "level": payload.get("level", "A2"),
            "interests": payload.get("interests", []),
            "learning_style": payload.get("learning_style", "visual"),
            "bio": payload.get("bio", ""),
            "available": payload.get("available", True),
            "registered_at": str(uuid.uuid4()),
        }
        self._profiles[profile["user_id"]] = profile
        logger.info(f"🤝 匹配画像注册: {profile['user_id'][:8]} {profile['native_language']}→{profile['target_language']}")
        return {"status": "ok", "profile": profile}

    # ── 查找学习伙伴 ──
    async def find_partners(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        limit = payload.get("limit", 10)
        user = self._profiles.get(user_id)
        if not user:
            return {"error": "请先注册匹配画像"}

        # 核心匹配逻辑：双向语言互补
        candidates = []
        for pid, profile in self._profiles.items():
            if pid == user_id or not profile.get("available", True):
                continue
            # 你教我母语，我教你我学的
            if (profile["native_language"] == user["target_language"]
                    and profile["target_language"] == user["native_language"]):
                score = settings.match_perfect_score  # 完美互补
            # 一方目标语言 = 另一方的语言
            elif (profile["native_language"] == user["target_language"]
                  or profile["target_language"] == user["native_language"]):
                score = settings.match_lang_swap_score
            else:
                score = settings.match_default_score

            # 兴趣加分
            common = set(profile.get("interests", [])) & set(user.get("interests", []))
            score += len(common) * settings.match_interest_bonus

            candidates.append({
                "user_id": pid,
                "match_score": min(score, 100),
                "native_language": profile["native_language"],
                "target_language": profile["target_language"],
                "level": profile.get("level", ""),
                "interests": profile.get("interests", []),
                "bio": profile.get("bio", ""),
            })

        candidates.sort(key=lambda x: x["match_score"], reverse=True)
        return {"candidates": candidates[:limit], "total": len(candidates)}

    # ── 配对（如同约定时匹配） ──
    async def match_pair(self, payload: dict) -> dict:
        user_a = payload["user_a"]
        user_b = payload["user_b"]
        if user_a not in self._profiles or user_b not in self._profiles:
            return {"error": "用户未注册"}
        match_id = str(uuid.uuid4())
        logger.info(f"💞 配对成功: {user_a[:8]} ↔ {user_b[:8]}")
        return {
            "status": "ok",
            "match_id": match_id,
            "user_a": user_a,
            "user_b": user_b,
        }

    # ── 列出已有匹配（占位） ──
    async def list_matches(self, payload: dict) -> dict:
        return {"matches": [], "message": "MVP阶段暂无持久化匹配历史"}
