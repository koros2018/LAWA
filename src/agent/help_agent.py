"""
LAWA HelpAgent — 互助系统

基于 HelpRequest/HelpResponse 模型：
- 发布求助帖
- 接单回答
- 采纳答案
- 金币结算
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from src.agent.base_agent import BaseAgent
from src.database import AsyncSessionLocal
from src.models.help import HelpRequest, HelpResponse


class HelpAgent(BaseAgent):
    """互助系统Agent"""

    def __init__(self):
        super().__init__("HelpAgent")

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "list")
        handlers = {
            "post": self.post_request,
            "respond": self.respond,
            "accept": self.accept_answer,
            "list": self.list_requests,
            "detail": self.get_detail,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"未知操作: {action}"}
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    # ── 模型 → 字典序列化 ──
    @staticmethod
    def _request_to_dict(req: HelpRequest) -> dict:
        return {
            "id": str(req.id),
            "user_id": str(req.user_id),
            "title": req.title,
            "content": req.content,
            "language": req.language,
            "tags": req.tags or [],
            "reward_coin": req.reward_coin,
            "status": req.status,
            "accepted_response_id": str(req.accepted_response_id) if req.accepted_response_id else None,
            "created_at": req.created_at.isoformat() if req.created_at else None,
            "updated_at": req.updated_at.isoformat() if req.updated_at else None,
        }

    @staticmethod
    def _response_to_dict(resp: HelpResponse) -> dict:
        return {
            "id": str(resp.id),
            "request_id": str(resp.request_id),
            "user_id": str(resp.user_id),
            "content": resp.content,
            "accepted": resp.accepted,
            "created_at": resp.created_at.isoformat() if resp.created_at else None,
        }

    # ── 发布求助 ──
    async def post_request(self, payload: dict) -> dict:
        req_id = uuid.uuid4()
        request = HelpRequest(
            id=req_id,
            user_id=payload["user_id"],
            title=payload["title"],
            content=payload.get("content", ""),
            language=payload.get("language", "en"),
            tags=payload.get("tags", []),
            reward_coin=payload.get("reward_coin", 0),
            status="open",
        )
        async with AsyncSessionLocal() as session:
            session.add(request)
            await session.commit()
            await session.refresh(request)
            result = self._request_to_dict(request)

        logger.info(f"🙋 求助帖发布: {result['title'][:30]} id={result['id'][:8]}")
        return {"status": "ok", "request": result}

    # ── 回答 ──
    async def respond(self, payload: dict) -> dict:
        req_id = payload["request_id"]
        async with AsyncSessionLocal() as session:
            stmt = select(HelpRequest).where(HelpRequest.id == req_id)
            result = await session.execute(stmt)
            request = result.scalar_one_or_none()
            if not request:
                return {"error": "求助帖不存在"}
            if request.status == "closed":
                return {"error": "该求助已关闭"}

            resp_id = uuid.uuid4()
            response = HelpResponse(
                id=resp_id,
                request_id=req_id,
                user_id=payload["user_id"],
                content=payload["content"],
                accepted=False,
            )
            session.add(response)
            await session.commit()
            await session.refresh(response)
            request_dict = self._request_to_dict(request)
            response_dict = self._response_to_dict(response)

        logger.info(f"💬 回答提交: {str(req_id)[:8]} by {str(payload['user_id'])[:8]}")
        return {"status": "ok", "request": request_dict, "response": response_dict}

    # ── 采纳答案 ──
    async def accept_answer(self, payload: dict) -> dict:
        req_id = payload["request_id"]
        resp_id = payload["response_id"]
        async with AsyncSessionLocal() as session:
            # 查询求助帖
            stmt = select(HelpRequest).where(HelpRequest.id == req_id)
            result = await session.execute(stmt)
            request = result.scalar_one_or_none()
            if not request:
                return {"error": "求助帖不存在"}
            if str(request.user_id) != str(payload["user_id"]):
                return {"error": "只有发起人可采纳"}

            # 查询回答
            resp_stmt = select(HelpResponse).where(HelpResponse.id == resp_id)
            resp_result = await session.execute(resp_stmt)
            response = resp_result.scalar_one_or_none()
            if not response:
                return {"error": "回答不存在"}

            # 更新求助帖状态
            request.status = "closed"
            request.accepted_response_id = uuid.UUID(resp_id)

            # 采纳该回答
            response.accepted = True

            await session.commit()
            await session.refresh(request)

            request_dict = self._request_to_dict(request)

            accepted_user = str(response.user_id)
            logger.info(f"✅ 采纳答案: {str(req_id)[:8]} → {str(resp_id)[:8]}")
            return {
                "status": "ok",
                "request": request_dict,
                "payout": {
                    "from": str(request.user_id),
                    "to": accepted_user,
                    "amount": request.reward_coin,
                }
            }

    # ── 列表 ──
    async def list_requests(self, payload: dict) -> dict:
        page = payload.get("page", 1)
        limit = payload.get("limit", 20)
        status_filter = payload.get("status")
        language = payload.get("language")
        user_id = payload.get("user_id")

        async with AsyncSessionLocal() as session:
            # 构建查询
            stmt = select(HelpRequest)

            if status_filter:
                stmt = stmt.where(HelpRequest.status == status_filter)
            if language:
                stmt = stmt.where(HelpRequest.language == language)
            if user_id:
                stmt = stmt.where(HelpRequest.user_id == user_id)

            # 获取总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0

            # 分页查询
            stmt = stmt.order_by(HelpRequest.created_at.desc())
            stmt = stmt.offset((page - 1) * limit).limit(limit)
            result = await session.execute(stmt)
            requests = result.scalars().all()

        items = [self._request_to_dict(r) for r in requests]
        return {
            "requests": items,
            "total": total,
            "page": page,
            "total_pages": max(1, (total + limit - 1) // limit),
        }

    # ── 详情 ──
    async def get_detail(self, payload: dict) -> dict:
        req_id = payload["request_id"]
        async with AsyncSessionLocal() as session:
            stmt = select(HelpRequest).where(HelpRequest.id == req_id)
            result = await session.execute(stmt)
            request = result.scalar_one_or_none()
            if not request:
                return {"error": "求助帖不存在"}

            # 查询关联的回答
            resp_stmt = select(HelpResponse).where(HelpResponse.request_id == req_id).order_by(HelpResponse.created_at)
            resp_result = await session.execute(resp_stmt)
            responses = resp_result.scalars().all()

            request_dict = self._request_to_dict(request)
            request_dict["responses"] = [self._response_to_dict(r) for r in responses]

            return {"request": request_dict}
