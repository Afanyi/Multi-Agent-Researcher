from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(..., alias="DATABASE_URL")
    celery_broker_url: str = Field(..., alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(..., alias="CELERY_RESULT_BACKEND")

    serper_api_key: str | None = Field(default=None, alias="SERPER_API_KEY")
    domain_default_allowlist: str | None = Field(default=None, alias="DOMAIN_DEFAULT_ALLOWLIST")


settings = Settings()
