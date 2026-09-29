from __future__ import annotations

from datetime import time
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram -----------------------------------------------------------
    bot_token: SecretStr
    # Telegram IDs that are always admins in the bot (even without an account).
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    # --- Storage ------------------------------------------------------------
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'bot.db'}"
    # Files uploaded through the website (Telegram files stay on Telegram).
    uploads_dir: Path = BASE_DIR / "data" / "uploads"

    # --- EduPage (public timetable; admins import group names from it) --------
    edupage_url: str = "https://ttpu.edupage.org"

    # --- Backups ---------------------------------------------------------------
    backup_enabled: bool = True
    backup_dir: Path = BASE_DIR / "backups"
    backup_time: str = "03:00"  # every day, in TIMEZONE
    backup_keep_days: int = 30
    # Encrypts the archive (AES-256 zip). Strongly recommended: backups hold passport data.
    backup_password: SecretStr | None = None

    # --- Website (staff panel) ----------------------------------------------
    web_enabled: bool = True
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    # Public URL of the panel, e.g. https://students.ttpu.uz (cookies become Secure on https)
    web_base_url: str = "http://localhost:8080"
    session_ttl_days: int = 7

    # --- Behaviour (defaults; admins can change them on the website) ---------
    notify_leaders: bool = True
    max_document_pages: int = 5
    min_student_age: int = 14
    max_student_age: int = 70
    timezone: str = "Asia/Tashkent"
    log_level: str = "INFO"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_ids(cls, v: object) -> object:
        if isinstance(v, str):
            return [int(x) for x in v.replace(";", ",").split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    @field_validator("backup_time")
    @classmethod
    def _check_time(cls, v: str) -> str:
        time.fromisoformat(v)  # HH:MM
        return v

    @field_validator("backup_password", mode="before")
    @classmethod
    def _empty_is_none(cls, v: object) -> object:
        return None if v == "" else v

    @property
    def web_secure(self) -> bool:
        return self.web_base_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
