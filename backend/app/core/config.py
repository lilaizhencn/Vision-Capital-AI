from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vision Capital AI"
    app_env: str = "local"
    app_secret_key: str = "change-me"
    cors_allowed_origins: str = "https://vision.tokdou.com,http://localhost:8090,http://localhost:5173"
    cors_allowed_origin_regex: str = r"^https://(?:[a-z0-9-]+\.)?vcai\.[a-z0-9-]+\.workers\.dev$"
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
    parse_stale_after_minutes: int = 30
    parse_recovery_batch_size: int = 100
    virus_scan_enabled: bool = False
    virus_scan_host: str = "clamav"
    virus_scan_port: int = 3310
    virus_scan_timeout_seconds: int = 30

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    ocr_model: str = "gpt-4o-mini"
    ocr_max_pages: int = 20
    pdf_table_max_pages: int = 40
    pdf_table_max_tables: int = 100
    pdf_table_max_characters: int = 500_000

    research_enabled: bool = True
    research_max_sources_per_run: int = 8
    research_download_max_bytes: int = 25 * 1024 * 1024
    research_request_timeout_seconds: int = 20
    research_user_agent: str = "VisionCapitalAI/1.0 research@vision.tokdou.com"
    research_auto_enrich_enabled: bool = True
    research_refresh_interval_hours: int = 168
    research_failure_retry_hours: int = 6
    research_lock_timeout_seconds: int = 1800
    research_scheduler_batch_size: int = 50

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
        if self.app_env.lower() != "production":
            return
        if self.app_secret_key == "change-me" or self.jwt_secret_key == "change-me":
            raise RuntimeError("APP_SECRET_KEY and JWT_SECRET_KEY must be changed in production")
        if not self.r2_enabled:
            raise RuntimeError("R2 configuration is required in production")
        if not self.database_url.startswith("postgresql"):
            raise RuntimeError("PostgreSQL is required in production")
        if not self.virus_scan_enabled:
            raise RuntimeError("Virus scanning must be enabled in production")
        if not self.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required in production")
        if "@" not in self.research_user_agent:
            raise RuntimeError("RESEARCH_USER_AGENT must include a contact email in production")

    @property
    def local_storage_absolute_path(self) -> Path:
        return self.local_storage_path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
