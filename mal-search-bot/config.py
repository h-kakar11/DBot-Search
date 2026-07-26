"""Configuration loading for mal-search-bot.

Loads the Discord bot token from the DISCORD_TOKEN environment variable first,
falling back to token.yaml. Loads non-secret settings from config.yaml with
environment variable overrides and sensible defaults.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load a .env file (if present) into the process environment.
load_dotenv(BASE_DIR / ".env")


class ConfigError(Exception):
    """Raised when required configuration (e.g. the bot token) is missing."""


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}


def get_token() -> str:
    """Return the Discord bot token.

    Resolution order:
      1. DISCORD_TOKEN environment variable (also populated from .env)
      2. token.yaml's `token` key
    """
    token = os.getenv("DISCORD_TOKEN")
    if token:
        return token.strip()

    token_file = BASE_DIR / "token.yaml"
    data = _load_yaml(token_file)
    token = data.get("token")
    if token:
        return str(token).strip()

    raise ConfigError(
        "No Discord bot token found. Set the DISCORD_TOKEN environment variable "
        "(or put it in a .env file), or create token.yaml from token.yaml.example."
    )


class Config:
    """Non-secret application settings loaded from config.yaml with env overrides."""

    def __init__(self) -> None:
        data = _load_yaml(BASE_DIR / "config.yaml")

        self.guild_id: Optional[int] = self._int_or_none(
            os.getenv("GUILD_ID", data.get("guild_id"))
        )

        self.jikan_base_url: str = os.getenv(
            "JIKAN_BASE_URL", data.get("jikan_base_url", "https://api.jikan.moe/v4")
        )

        self.rate_limit_per_second: float = float(
            os.getenv(
                "JIKAN_RATE_LIMIT_PER_SECOND",
                data.get("rate_limit_per_second", 3),
            )
        )

        self.rate_limit_per_minute: int = int(
            os.getenv(
                "JIKAN_RATE_LIMIT_PER_MINUTE",
                data.get("rate_limit_per_minute", 60),
            )
        )

        self.max_retries: int = int(
            os.getenv("JIKAN_MAX_RETRIES", data.get("max_retries", 3))
        )

        self.log_level: str = os.getenv(
            "LOG_LEVEL", data.get("log_level", "INFO")
        )

    @staticmethod
    def _int_or_none(value: Any) -> Optional[int]:
        if value in (None, "", "null"):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


config = Config()
