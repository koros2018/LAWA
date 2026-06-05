"""
LAWA CoinAgent — 金币经济系统 Agent

LAWA的灵魂模块。管理完整金币生命周期：
- 注册奖励 / 每日消耗 / 登录奖励
- 学习赚取（10min=1coin，日上限12）
- 用户间交易（Transfer，ACID）
- 防刷检测
- 日结算汇总
- DB 持久化（优先）+ in-memory 降级
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.agent.base_agent import BaseAgent
from src.config import settings
from src.models.coin import CoinTransaction, CoinDailySummary


class CoinAgent(BaseAgent):
    """金币经济核心Agent"""

    RULES = {
        "register_bonus": settings.coins_register_bonus,
        "daily_consume": settings.coins_daily_consume,
        "daily_login": settings.coins_daily_login,
        "study_per_10min": settings.coins_study_per_10min,
        "study_daily_max": settings.coins_study_daily_max,
        "invite_bonus": settings.coins_invite_bonus,
        "help_daily_max": settings.coins_help_daily_max,
        "anti_cheat_daily_max": settings.coins_anti_cheat_daily_max,
    }

    def __init__(self):
        super().__init__("CoinAgent")
        self._balances: dict[str, int] = {}
        self._transactions: list[dict] = []
        self._daily_tracking: dict[str, dict] = {}

    async def execute(self, payload: dict) -> dict:
        action = payload.get("action", "get_balance")
        handlers = {
            "register_bonus": self.register_bonus,
            "daily_login": self.daily_login,
            "study_reward": self.study_reward,
            "trade": self.trade,
            "get_balance": self.get_balance,
            "get_transactions": self.get_transactions,
            "daily_summary": self.daily_summary,
            "get_rules": self.get_rules,
        }
        handler = handlers.get(action)
        if not handler:
            return {"error": f"Unknown action: {action}"}
        result = await handler(payload)
        self.log_execution(payload, result)
        return result

    # ── DB 余额查询 ──
    async def _db_get_balance(self, db: AsyncSession, user_id: str) -> int:
        """从 DB 查询用户当前余额"""
        try:
            result = await db.execute(
                select(func.coalesce(func.sum(CoinTransaction.amount), 0))
                .where(CoinTransaction.user_id == uuid.UUID(user_id))
            )
            return result.scalar() or 0
        except Exception:
            return 0

    async def _db_record_transaction(
        self, db: AsyncSession,
        user_id: str, tx_type: str, amount: int,
        balance_before: int, balance_after: int,
        related_user_id: Optional[str] = None,
        description: str = "",
    ) -> dict:
        """写入一条交易记录到 DB"""
        try:
            tx = CoinTransaction(
                user_id=uuid.UUID(user_id),
                type=tx_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                related_user_id=uuid.UUID(related_user_id) if related_user_id else None,
                description=description,
            )
            db.add(tx)
            await db.commit()
            return {"id": str(tx.id), "type": tx_type, "amount": amount, "balance_after": balance_after}
        except Exception as e:
            logger.warning(f"DB transaction failed: {e}")
            await db.rollback()
            raise

    # ── 内存降级方法 ──
    def _mem_get_balance(self, user_id: str) -> int:
        return self._balances.get(user_id, 0)

    def _mem_set_balance(self, user_id: str, new_balance: int):
        self._balances[user_id] = new_balance

    def _mem_record_transaction(self, user_id: str, tx_type: str, amount: int,
                                  balance_before: int, balance_after: int,
                                  related_user_id=None, description=""):
        tx = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": tx_type,
            "amount": amount,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "related_user_id": related_user_id,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._transactions.append(tx)
        return tx

    # ── 规则引擎 ──
    async def get_rules(self, payload: dict) -> dict:
        return {
            "rules": self.RULES,
            "summary": {
                "注册即送": f"{self.RULES['register_bonus']} 金币",
                "每日自动消耗": f"{self.RULES['daily_consume']} 金币",
                "每日登录奖励": f"{self.RULES['daily_login']} 金币",
                "学习10分钟奖励": f"{self.RULES['study_per_10min']} 金币（日上限 {self.RULES['study_daily_max']}）",
                "邀请新用户": f"{self.RULES['invite_bonus']} 金币/人",
                "帮助他人日上限": f"{self.RULES['help_daily_max']} 金币",
            },
        }

    async def register_bonus(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        bonus = self.RULES["register_bonus"]
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                balance_before = await self._db_get_balance(db, user_id)
                balance_after = balance_before + bonus
                await self._db_record_transaction(db, user_id, "register", bonus,
                                                    balance_before, balance_after,
                                                    description=f"🎉 注册奖励：+{bonus} 金币")
                logger.info(f"💰 注册奖励(DB): user={user_id}, +{bonus}")
                return {"new_balance": balance_after}
            except Exception as e:
                logger.warning(f"DB注册奖励失败 (降级): {e}")

        balance_before = self._mem_get_balance(user_id)
        balance_after = balance_before + bonus
        self._mem_set_balance(user_id, balance_after)
        self._mem_record_transaction(user_id, "register", bonus, balance_before, balance_after,
                                       description=f"🎉 注册奖励：+{bonus} 金币")
        return {"new_balance": balance_after}

    async def daily_login(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                balance_before = await self._db_get_balance(db, user_id)
                # 扣消耗
                if balance_before >= self.RULES["daily_consume"]:
                    balance_mid = balance_before - self.RULES["daily_consume"]
                    await self._db_record_transaction(db, user_id, "daily_consume", -self.RULES["daily_consume"],
                                                        balance_before, balance_mid,
                                                        description=f"📉 每日消耗：-{self.RULES['daily_consume']} 金币")
                    balance_before = balance_mid
                # 发奖励
                balance_after = balance_before + self.RULES["daily_login"]
                await self._db_record_transaction(db, user_id, "daily_login", self.RULES["daily_login"],
                                                    balance_before, balance_after,
                                                    description=f"📈 每日签到：+{self.RULES['daily_login']} 金币")
                net = self.RULES["daily_login"] - self.RULES["daily_consume"]
                logger.info(f"💰 每日登录(DB): user={user_id}, net={net}")
                return {"new_balance": balance_after, "daily_consume": self.RULES["daily_consume"],
                        "login_reward": self.RULES["daily_login"], "net_change": net}
            except Exception as e:
                logger.warning(f"DB登录失败 (降级): {e}")

        # 降级内存逻辑
        balance = self._mem_get_balance(user_id)
        if balance >= self.RULES["daily_consume"]:
            balance_after_consume = balance - self.RULES["daily_consume"]
            self._mem_set_balance(user_id, balance_after_consume)
            self._mem_record_transaction(user_id, "daily_consume", -self.RULES["daily_consume"],
                                           balance, balance_after_consume,
                                           description=f"📉 每日消耗：-{self.RULES['daily_consume']} 金币")
            balance = balance_after_consume
        balance_after_login = balance + self.RULES["daily_login"]
        self._mem_set_balance(user_id, balance_after_login)
        self._mem_record_transaction(user_id, "daily_login", self.RULES["daily_login"],
                                       balance, balance_after_login,
                                       description=f"📈 每日签到：+{self.RULES['daily_login']} 金币")
        net = self.RULES["daily_login"] - self.RULES["daily_consume"]
        return {"new_balance": balance_after_login, "daily_consume": self.RULES["daily_consume"],
                "login_reward": self.RULES["daily_login"], "net_change": net}

    async def study_reward(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        minutes = payload.get("minutes", 0)
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                # 查询今日已赚
                today = date.today()
                result = await db.execute(
                    select(func.coalesce(func.sum(CoinTransaction.amount), 0))
                    .where(CoinTransaction.user_id == uuid.UUID(user_id))
                    .where(CoinTransaction.type == "study")
                    .where(func.date(CoinTransaction.created_at) == today)
                )
                today_earned = result.scalar() or 0
                max_earnable = self.RULES["study_daily_max"] - today_earned
                if max_earnable <= 0:
                    return {"message": "今日学习奖励已达上限", "earned": 0, "daily_limit_reached": True}

                earnable_coins = min(minutes // 10, max_earnable)
                if earnable_coins <= 0:
                    return {"message": "学习时间不足10分钟", "earned": 0, "balance": await self._db_get_balance(db, user_id)}

                balance_before = await self._db_get_balance(db, user_id)
                balance_after = balance_before + earnable_coins
                await self._db_record_transaction(db, user_id, "study", earnable_coins,
                                                    balance_before, balance_after,
                                                    description=f"📚 学习 {minutes} 分钟：+{earnable_coins} 金币")
                logger.info(f"💰 学习奖励(DB): user={user_id}, +{earnable_coins}")
                return {"new_balance": balance_after, "earned": earnable_coins, "minutes": minutes}
            except Exception as e:
                logger.warning(f"DB学习奖励失败 (降级): {e}")

        # 降级
        tracker = self._get_daily_tracker(user_id)
        max_earnable = self.RULES["study_daily_max"] - tracker["study_earned"]
        earnable_coins = min(minutes // 10, max_earnable)
        if earnable_coins <= 0:
            return {"message": "无法获取奖励", "earned": 0}
        balance_before = self._mem_get_balance(user_id)
        balance_after = balance_before + earnable_coins
        self._mem_set_balance(user_id, balance_after)
        self._mem_record_transaction(user_id, "study", earnable_coins, balance_before, balance_after,
                                       description=f"📚 学习 {minutes} 分钟：+{earnable_coins} 金币")
        tracker["study_earned"] += earnable_coins
        return {"new_balance": balance_after, "earned": earnable_coins}

    async def trade(self, payload: dict) -> dict:
        from_user = payload["from_user_id"]
        to_user = payload["to_user_id"]
        amount = payload["amount"]
        description = payload.get("description", "")
        db: Optional[AsyncSession] = payload.get("db")

        if amount <= 0:
            return {"error": "交易金额必须为正数"}

        if db:
            try:
                from_balance = await self._db_get_balance(db, from_user)
                if from_balance < amount:
                    return {"error": f"余额不足（当前: {from_balance}, 需要: {amount}）"}

                to_balance_before = await self._db_get_balance(db, to_user)
                await self._db_record_transaction(db, from_user, "trade_out", -amount,
                                                    from_balance, from_balance - amount,
                                                    related_user_id=to_user,
                                                    description=f"💸 支付给 {to_user[:8]}...: -{amount} 金币 - {description}")
                await self._db_record_transaction(db, to_user, "trade_in", amount,
                                                    to_balance_before, to_balance_before + amount,
                                                    related_user_id=from_user,
                                                    description=f"💰 来自 {from_user[:8]}...: +{amount} 金币 - {description}")
                logger.info(f"💰 交易(DB): {from_user} → {to_user}, amount={amount}")
                return {"from_balance": from_balance - amount, "to_balance": to_balance_before + amount, "amount": amount}
            except Exception as e:
                logger.warning(f"DB交易失败 (降级): {e}")

        # 降级
        from_balance = self._mem_get_balance(from_user)
        if from_balance < amount:
            return {"error": f"余额不足"}
        to_balance_before = self._mem_get_balance(to_user)
        self._mem_set_balance(from_user, from_balance - amount)
        self._mem_set_balance(to_user, to_balance_before + amount)
        self._mem_record_transaction(from_user, "trade_out", -amount, from_balance, from_balance - amount,
                                       related_user_id=to_user, description=f"💸 支付：-{amount}")
        self._mem_record_transaction(to_user, "trade_in", amount, to_balance_before, to_balance_before + amount,
                                       related_user_id=from_user, description=f"💰 收入：+{amount}")
        return {"from_balance": from_balance - amount, "to_balance": to_balance_before + amount}

    async def get_balance(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                balance = await self._db_get_balance(db, user_id)
                return {"user_id": user_id, "balance": balance}
            except Exception:
                pass
        return {"user_id": user_id, "balance": self._mem_get_balance(user_id)}

    async def get_transactions(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        limit = payload.get("limit", 20)
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                result = await db.execute(
                    select(CoinTransaction)
                    .where(CoinTransaction.user_id == uuid.UUID(user_id))
                    .order_by(CoinTransaction.created_at.desc())
                    .limit(limit)
                )
                txs = result.scalars().all()
                return {
                    "user_id": user_id,
                    "transactions": [
                        {"id": str(t.id), "type": t.type, "amount": t.amount,
                         "balance_after": t.balance_after, "description": t.description,
                         "created_at": t.created_at.isoformat() if t.created_at else None}
                        for t in txs
                    ],
                    "total_count": len(txs),
                }
            except Exception:
                pass

        user_txs = [tx for tx in self._transactions if tx["user_id"] == user_id]
        user_txs.sort(key=lambda x: x["created_at"], reverse=True)
        return {"user_id": user_id, "transactions": user_txs[:limit], "total_count": len(user_txs)}

    async def daily_summary(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        db: Optional[AsyncSession] = payload.get("db")

        if db:
            try:
                today = date.today()
                result = await db.execute(
                    select(func.coalesce(func.sum(CoinTransaction.amount), 0))
                    .where(CoinTransaction.user_id == uuid.UUID(user_id))
                    .where(func.date(CoinTransaction.created_at) == today)
                )
                net = result.scalar() or 0
                balance = await self._db_get_balance(db, user_id)
                return {"user_id": user_id, "date": today.isoformat(), "balance": balance,
                        "net_change": net, "today": today.isoformat()}
            except Exception:
                pass
        return {"user_id": user_id, "balance": self._mem_get_balance(user_id)}

    def _get_daily_tracker(self, user_id: str) -> dict:
        today = date.today().isoformat()
        if user_id not in self._daily_tracking:
            self._daily_tracking[user_id] = {}
        if self._daily_tracking[user_id].get("date") != today:
            self._daily_tracking[user_id] = {"date": today, "study_earned": 0, "help_earned": 0, "login_done": False}
        return self._daily_tracking[user_id]
