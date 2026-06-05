"""
测试：配置系统 — Settings 加载与默认值
"""
from src.config import Settings


class TestSettingsDefaults:
    def test_app_defaults(self):
        s = Settings()
        assert s.app_name == "LAWA"
        assert s.app_version == "0.1.0"
        assert s.api_port == 6288

    def test_database_defaults(self):
        s = Settings()
        assert s.db_host == "localhost"
        assert s.db_port == 5432
        assert s.db_user == "lawa"

    def test_jwt_defaults(self):
        s = Settings()
        assert s.jwt_algorithm == "HS256"
        assert s.jwt_expire_minutes == 60 * 24 * 7  # 7 days

    def test_coin_defaults(self):
        s = Settings()
        assert s.coins_register_bonus == 1000
        assert s.coins_daily_login == 10
        assert s.coins_daily_consume == 10
        assert s.coins_anti_cheat_daily_max == 200

    def test_llm_defaults(self):
        s = Settings()
        assert s.llm_default_provider == "longcat"
        assert s.llm_temperature == 0.7
        assert s.llm_max_tokens == 4096


class TestSettingsProperties:
    def test_sqlite_url(self):
        s = Settings(db_use_sqlite=True, sqlite_path="./data/test.db")
        url = s.database_url
        assert "sqlite+aiosqlite:///" in url
        assert "test.db" in url

    def test_postgres_url(self):
        s = Settings(
            db_use_sqlite=False,
            db_host="pg.example.com",
            db_port=5432,
            db_user="admin",
            db_password="***",
            db_name="lawadb",
        )
        url = s.database_url
        assert "postgresql+asyncpg://" in url
        assert "admin:***@pg.example.com:5432/lawadb" in url

    def test_redis_url_no_password(self):
        s = Settings(redis_password=None)
        assert "redis://localhost:6379/0" in s.redis_url

    def test_redis_url_with_password(self):
        s = Settings(redis_password="***", redis_host="cache", redis_port=6380, redis_db=1)
        assert "redis://:***@cache:6380/1" in s.redis_url
