from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    workspace: Path = Path(".")

    github_access_token: SecretStr
    openrouter_api_key: SecretStr


settings = Settings()  # type: ignore
