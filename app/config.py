from __future__ import annotations
from functools import lru_cache
from typing import List
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SmartApprove"
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite:///./smartapprove.db"
    ADMIN_EMAIL: str = "admin@smartapprove.com"
    ADMIN_PASSWORD: str = "Admin1234"
    UPLOAD_DIR: str = "app/static/uploads"
    MAX_UPLOAD_MB: int = 10

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def allowed_extensions(self) -> List[str]:
        return ["pdf", "docx", "xlsx", "png", "jpg", "jpeg"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
