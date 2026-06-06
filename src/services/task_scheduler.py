"""
LAWA 任务调度服务
处理过期任务、截止日期检查
"""
from datetime import datetime, timezone
from sqlalchemy import select, update
from loguru import logger
from src.database.main import AsyncSessionLocal
from src.models.task import Task, TaskStatus


async def enforce_task_deadlines() -> dict:
    """检查并取消所有已过期的任务
    
    将 deadline 已过且状态为 open 或 assigned 的任务标记为 cancelled.
    返回处理结果统计.
    """
    now = datetime.now(timezone.utc)
    
    async with AsyncSessionLocal() as session:
        # 查询所有过期但未关闭的任务
        result = await session.execute(
            select(Task).where(
                Task.deadline.isnot(None),
                Task.deadline < now,
                Task.status.in_([TaskStatus.open, TaskStatus.assigned])
            )
        )
        expired_tasks = result.scalars().all()
        
        if not expired_tasks:
            logger.info("[TaskScheduler] 无过期任务")
            return {"cancelled": 0, "message": "无过期任务"}
        
        # 批量取消
        task_ids = [t.id for t in expired_tasks]
        await session.execute(
            update(Task)
            .where(Task.id.in_(task_ids))
            .values(status=TaskStatus.cancelled, updated_at=now)
        )
        await session.commit()
        
        for t in expired_tasks:
            logger.info(f"[TaskScheduler] ⏰ 过期取消: {t.title[:30]} (deadline={t.deadline})")
        
        return {
            "cancelled": len(expired_tasks),
            "task_ids": [str(tid) for tid in task_ids],
            "message": f"已取消 {len(expired_tasks)} 个过期任务"
        }
