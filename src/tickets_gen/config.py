from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    github_token: SecretStr | None = None
    github_api_url: str = "https://api.github.com"

    opencode_command: str = "opencode"

    model_config = SettingsConfigDict(
        env_prefix="TICKETSGEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()