"""
LAWA FastAPI 应用入口

服务端口: 6288
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from src.config import settings
from src.database.main import init_db, close_db
from src.routes import auth_router, assessment_router, persona_plan_router, coin_router, companion_router, task_router, community_router, rpg_router, tutor_router, vocabulary_router, llm_config_router
import src.models  # 确保所有模型在 init_db 前注册


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info(f"🚀 {settings.app_name} v{settings.app_version} 启动中...")
    logger.info(f"   端口: {settings.api_port}")
    logger.info(f"   数据库: {settings.db_host}:{settings.db_port}/{settings.db_name}")

    # 启动时初始化数据库
    await init_db()
    logger.info("✅ 数据库连接成功")

    yield

    # 关闭时清理
    await close_db()
    logger.info("👋 LAWA 服务关闭")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(assessment_router)
app.include_router(persona_plan_router)
app.include_router(coin_router)
app.include_router(companion_router)
app.include_router(task_router)
app.include_router(community_router)
app.include_router(rpg_router)
app.include_router(tutor_router)
app.include_router(vocabulary_router)
app.include_router(llm_config_router)


# ── 健康检查 ──
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/api/v1/health")
async def api_health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "database": settings.db_name,
    }
