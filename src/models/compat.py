"""
LAWA 数据库兼容层
针对 SQLite 和 PostgreSQL 提供统一的字段类型
"""
import uuid as _uuid
from sqlalchemy.types import TypeDecorator, String, JSON as SAJSON
from src.config import settings

# ── Portable UUID ──
if settings.db_use_sqlite:
    # SQLite: UUID → String(36)
    class _UUID(TypeDecorator):
        impl = String(36)
        cache_ok = True

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if isinstance(value, _uuid.UUID):
                return str(value)
            return str(value)

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            if isinstance(value, _uuid.UUID):
                return value
            try:
                return _uuid.UUID(value)
            except (ValueError, AttributeError):
                return value

    UUID = _UUID

    # SQLite: ARRAY → JSON
    def _ARRAY(item_type):
        return SAJSON

    ARRAY = _ARRAY

else:
    # PostgreSQL: native types
    from sqlalchemy.dialects.postgresql import UUID, ARRAY  # noqa: F401
