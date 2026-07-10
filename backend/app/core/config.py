from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vision Capital AI"
    app_env: str = "local"
    app_secret_key: str = "change-me"
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:5174"
    auto_create_tables: bool = False
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/vision_capital_ai"
    redis_url: str = "redis://localhost:6379/0"
    database_connect_timeout_seconds: int = 1

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    r2_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    r2_public_base_url: str | None = None
    r2_presigned_url_expiry_seconds: int = 900
    upload_multipart_threshold_bytes: int = 10 * 1024 * 1024
    upload_part_size_bytes: int = 8 * 1024 * 1024
    max_upload_size_bytes: int = 1024 * 1024 * 1024
    max_parse_retries: int = 3

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    ocr_model: str = "gpt-4o-mini"
    ocr_max_pages: int = 20

    local_storage_path: Path = Path("./storage_data")
    chunk_size: int = 1200
    chunk_overlap: int = 200
    embedding_dimension: int = 1536
    celery_task_always_eager: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def r2_enabled(self) -> bool:
        return bool(
            self.r2_endpoint_url
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket_name
        )

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]

    def validate_production(self) -> None:
        if self.app_env.lower() == "production" and self.app_secret_key == "change-me":
            raise RuntimeError("APP_SECRET_KEY must be changed in production")

    @property
    def local_storage_absolute_path(self) -> Path:
        return self.local_storage_path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
