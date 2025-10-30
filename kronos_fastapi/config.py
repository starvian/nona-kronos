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
    app_name: str = "Kronos FastAPI Service"
    log_level: str = "INFO"

    model_id: Optional[str] = None
    tokenizer_id: Optional[str] = None
    model_local_path: str = "/data/ws/kronos/models"
    device: str = "cpu"

    max_context: int = 512
    default_lookback: int = 400
    default_pred_len: int = 120
    default_temperature: float = 1.0
    default_top_k: int = 0
    default_top_p: float = 0.9
    default_sample_count: int = 1
    clip_value: float = 5.0

    enable_metrics: bool = True

    # Security settings
    security_enabled: bool = False  # Changed default to False for development
    container_whitelist: str = "localhost,frontend-app,worker-service,scheduler"

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 100

    # Request limits
    max_request_size_mb: int = 10

    # Timeout settings (Phase 3)
    inference_timeout: int = 240
    request_timeout: int = 300
    startup_timeout: int = 300

    if PYDANTIC_V2:
        model_config = SettingsConfigDict(
            env_prefix="KRONOS_",
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False
        )
    else:
        class Config:
            env_prefix = "KRONOS_"
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

    @field_validator("device")
    @classmethod
    def validate_device(cls, value: str) -> str:
        return value.strip()


@lru_cache()
def get_settings() -> Settings:
    return Settings()
