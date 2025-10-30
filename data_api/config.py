"""
Configuration management for Data API service.
"""

from functools import lru_cache
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import field_validator
    PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseSettings, Field, validator as field_validator
    PYDANTIC_V2 = False


class Settings(BaseSettings):
    """Data API Service Configuration"""

    # Service info
    app_name: str = "Kronos Data API Service"
    log_level: str = "INFO"

    # ClickHouse connection
    clickhouse_host: str = "192.168.1.110"  # Local machine
    clickhouse_port: int = 19999
    clickhouse_user: str = "webss"
    clickhouse_password: str = "webss"
    clickhouse_database: str = "default"

    # Connection pool
    clickhouse_pool_size: int = 10
    clickhouse_max_retries: int = 3
    clickhouse_retry_delay: float = 1.0
    clickhouse_timeout: int = 30

    # API settings
    api_port: int = 8001
    api_host: str = "0.0.0.0"

    # Data limits
    max_candles_per_request: int = 10000
    default_candles_limit: int = 128

    # Cache settings (Phase 3 - optional)
    cache_enabled: bool = False
    cache_ttl_seconds: int = 60

    if PYDANTIC_V2:
        model_config = SettingsConfigDict(
            env_prefix="DATA_API_",
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False
        )
    else:
        class Config:
            env_prefix = "DATA_API_"
            env_file = ".env"
            env_file_encoding = "utf-8"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in valid_levels:
            raise ValueError(f"Unsupported log level: {value}")
        return normalized


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
