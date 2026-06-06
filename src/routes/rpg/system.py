"""总架构师（系统监督）路由"""
from fastapi import APIRouter
from src.agent.architect_agent import ArchitectAgent

router = APIRouter(prefix="/system", tags=["RPG-System"])
architect_agent = ArchitectAgent()


@router.get("/health")
async def system_health():
    """系统健康检查"""
    return await architect_agent.run({"action": "health"})


@router.get("/dashboard")
async def system_dashboard():
    """数据面板"""
    return await architect_agent.run({"action": "dashboard"})


@router.get("/audit")
async def system_audit():
    """代码审查"""
    return await architect_agent.run({"action": "audit"})


@router.get("/report")
async def system_report():
    """完整巡检报告"""
    return await architect_agent.run({"action": "report"})