"""
LAWA 配置中心
基于 pydantic-settings，支持 .env 环境变量覆盖
"""
from pydantic_settings import BaseSettings
from typing import Optional
from loguru import logger
import os


class Settings(BaseSettings):
    # ── 应用 ──
    app_name: str = "LAWA"
    app_version: str = "0.1.0"
    debug: bool = True

    # ── 服务器 ──
    api_host: str = "0.0.0.0"
    api_port: int = 6288
    cors_origins: list[str] = ["http://localhost:6289", "http://127.0.0.1:6289"]

    # ── 数据库 ──
    db_use_sqlite: bool = True  # True=SQLite(dev/test), False=PostgreSQL(prod)

    # PostgreSQL (prod)
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "lawa"
    db_password: str = "lawa_dev"
    db_name: str = "lawa"
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # SQLite (dev/test)
    sqlite_path: str = "./data/lawa.db"

    @property
    def database_url(self) -> str:
        if self.db_use_sqlite:
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def database_url_sync(self) -> str:
        if self.db_use_sqlite:
            return f"sqlite:///{self.sqlite_path}"
        return f"postgresql+psycopg2://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # ── Redis ──
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ── JWT ──
    jwt_secret: Optional[str] = None  # None = 生产环境需要手动设置
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    @property
    def effective_jwt_secret(self) -> str:
        """获取有效的JWT密钥，开发环境提供默认值，生产环境必须配置"""
        env_secret = os.getenv("JWT_SECRET")
        if env_secret:
            return env_secret
        if self.jwt_secret:
            return self.jwt_secret
        if self.debug:
            logger.warning("⚠️ JWT_SECRET 使用开发默认值，生产环境请设置 JWT_SECRET 环境变量！")
            return "lawa-dev-secret-change-in-production"
        raise ValueError("JWT_SECRET 未设置！生产环境必须配置 JWT_SECRET 环境变量。")

    # ── LLM 提供商 ──
    llm_default_provider: str = "longcat"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 120

    # ── LongCat ──
    llm_longcat_key: Optional[str] = None
    llm_longcat_base_url: str = "https://api.longcat.chat/openai/v1"
    llm_longcat_model: str = "LongCat-2.0-Preview"

    # ── OpenCode (kimi-k2.6) ──
    llm_opencode_key: Optional[str] = None
    llm_opencode_base_url: str = "https://opencode.ai/zen/go/v1"
    llm_opencode_model: str = "kimi-k2.6"

    # ── Ollama (本地) ──
    ollama_host: str = "http://localhost:11435"
    ollama_model: str = "llama3.2"

    # ── DeepSeek ──
    llm_deepseek_key: Optional[str] = None
    llm_deepseek_base_url: str = "https://api.deepseek.com/v1"
    llm_deepseek_model: str = "deepseek-chat"

    # ── 金币系统 ──
    coins_register_bonus: int = 1000
    coins_daily_consume: int = 10
    coins_daily_login: int = 10
    coins_study_per_10min: int = 1
    coins_study_daily_max: int = 12
    coins_invite_bonus: int = 500
    coins_help_daily_max: int = 50
    coins_anti_cheat_daily_max: int = 200

    # ── Agent 阈值配置 ──
    # Assessment
    assess_questions_per_dimension: int = 3
    assess_min_questions_for_report: int = 5
    assess_correctness_threshold: int = 7  # score >= this → correct
    # Matching
    match_perfect_score: int = 100
    match_lang_swap_score: int = 70
    match_default_score: int = 30
    match_interest_bonus: int = 5
    # Persona
    persona_strength_threshold: int = 8  # score >= → strength
    persona_weakness_threshold: int = 6  # score < → weakness
    # Plan adjustment
    plan_completion_low: float = 0.3
    plan_completion_moderate: float = 0.6
    plan_completion_high: float = 0.9
    plan_rating_low: int = 3
    plan_rating_high: float = 4.5
    plan_time_overflow_ratio: float = 1.5

    # ── 向量数据库 (ChromaDB) ──
    chroma_host: str = "localhost"
    chroma_port: int = 8002
    chroma_persist_dir: str = "./data/chroma"

    # ── 日志 ──
    log_level: str = "INFO"
    log_dir: str = "./logs"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow"
    }


settings = Settings()
