from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./data/conditionwatch.db"
    jwt_secret: str = Field(default="development-only-change-me", min_length=20)
    jwt_issuer: str = "conditionwatch-api"
    access_token_minutes: int = 60 * 24 * 30
    public_api_url: str = "http://localhost:8000"
    mobile_redirect_uri: str = "conditionwatch://auth"

    openai_api_key: str | None = None
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"
    openai_vision_model: str = "gpt-5.6-luna"
    openai_condition_model: str = "gpt-5.6-luna"
    openai_store_responses: bool = False

    firebase_credentials_json: str | None = None
    firebase_project_id: str | None = None

    max_audio_bytes: int = 12 * 1024 * 1024
    max_frame_bytes: int = 4 * 1024 * 1024
    default_sample_interval_ms: int = 1500
    min_sample_interval_ms: int = 750
    vision_match_threshold: float = 0.82
    cors_origins: list[str] = ["http://localhost:8000"]

    @field_validator("jwt_secret")
    @classmethod
    def production_secret(cls, value: str, info):
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
