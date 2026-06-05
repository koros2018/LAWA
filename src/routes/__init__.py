"""LAWA API 路由"""
from src.routes.auth import router as auth_router
from src.routes.assessment import router as assessment_router
from src.routes.persona_plan import router as persona_plan_router
from src.routes.coin import router as coin_router
from src.routes.companion import router as companion_router
from src.routes.task import router as task_router
from src.routes.community import router as community_router
from src.routes.tutor import router as tutor_router
from src.routes.rpg import router as rpg_router
from src.routes.vocabulary import router as vocabulary_router
from src.routes.llm_config import router as llm_config_router

__all__ = ["auth_router", "assessment_router", "persona_plan_router", "coin_router", "companion_router", "task_router", "community_router", "tutor_router", "rpg_router", "vocabulary_router", "llm_config_router"]
