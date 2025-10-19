from functools import lru_cache
from typing import Optional

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field, field_validator
except ImportError:
    from pydantic import BaseSettings, Field, validator as field_validator


class Settings(BaseSettings):
    app_name: str = Field("Kronos FastAPI Service", env="KRONOS_APP_NAME")
    log_level: str = Field("INFO", env="KRONOS_LOG_LEVEL")

    model_id: Optional[str] = Field(None, env="KRONOS_MODEL_ID")
    tokenizer_id: Optional[str] = Field(None, env="KRONOS_TOKENIZER_ID")
    model_local_path: str = Field("/data/ws/kronos/models", env="KRONOS_MODEL_PATH")
    device: str = Field("cpu", env="KRONOS_DEVICE")

    max_context: int = Field(512, env="KRONOS_MAX_CONTEXT")
    default_lookback: int = Field(400, env="KRONOS_DEFAULT_LOOKBACK")
    default_pred_len: int = Field(120, env="KRONOS_DEFAULT_PRED_LEN")
    default_temperature: float = Field(1.0, env="KRONOS_DEFAULT_TEMPERATURE")
    default_top_k: int = Field(0, env="KRONOS_DEFAULT_TOP_K")
    default_top_p: float = Field(0.9, env="KRONOS_DEFAULT_TOP_P")
    default_sample_count: int = Field(1, env="KRONOS_DEFAULT_SAMPLE_COUNT")
    clip_value: float = Field(5.0, env="KRONOS_CLIP_VALUE")

    enable_metrics: bool = Field(True, env="KRONOS_ENABLE_METRICS")

    # Security settings
    security_enabled: bool = Field(True, env="KRONOS_SECURITY_ENABLED")
    container_whitelist: str = Field(
        "localhost,frontend-app,worker-service,scheduler",
        env="KRONOS_CONTAINER_WHITELIST"
    )

    # Rate limiting
    rate_limit_enabled: bool = Field(True, env="KRONOS_RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(100, env="KRONOS_RATE_LIMIT_PER_MINUTE")

    # Request limits
    max_request_size_mb: int = Field(10, env="KRONOS_MAX_REQUEST_SIZE_MB")

    # Timeout settings (Phase 3)
    # 注意: 增加默认值以支持长序列预测
    inference_timeout: int = Field(default=240, env="KRONOS_INFERENCE_TIMEOUT")
    request_timeout: int = Field(default=300, env="KRONOS_REQUEST_TIMEOUT")
    startup_timeout: int = Field(default=300, env="KRONOS_STARTUP_TIMEOUT")

    class Config:
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
