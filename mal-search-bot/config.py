"""Centralized configuration and environment loading for mal-search-bot.

All configuration is sourced from environment variables (optionally loaded
from a local .env file via python-dotenv). No secrets are ever hardcoded.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load a .env file (if present) into the process environment.
load_dotenv(BASE_DIR / ".env")


class ConfigError(Exception):
    """Raised when required configuration (e.g. the bot token) is missing or invalid."""


def _int_or_none(value: Optional[str]) -> Optional[int]:
    """Parse an optional environment variable string into an int, or None."""
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _float_env(name: str, default: float) -> float:
    """Read a float environment variable, falling back to a default."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    """Read an int environment variable, falling back to a default."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Application settings resolved once at process startup.

    Attributes:
        discord_token: The bot's Discord token (required, from DISCORD_TOKEN).
        guild_id: Optional guild ID for fast, guild-scoped slash command sync
            during development. If unset, commands sync globally.
        jikan_base_url: Base URL for the Jikan v4 API.
        rate_limit_per_second: Max Jikan requests allowed per rolling second.
        rate_limit_per_minute: Max Jikan requests allowed per rolling minute.
        max_retries: Max retry attempts for Jikan 5xx errors/timeouts.
        log_level: Root logging level name (e.g. "INFO", "DEBUG").
    """

    discord_token: str
    guild_id: Optional[int]
    jikan_base_url: str
    rate_limit_per_second: float
    rate_limit_per_minute: int
    max_retries: int
    log_level: str


def load_settings() -> Settings:
    """Load and validate application settings from environment variables.

    Raises:
        ConfigError: If the required DISCORD_TOKEN is missing.
    """
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "DISCORD_TOKEN environment variable is not set. Copy .env.example to .env "
            "and fill in your bot token, or export DISCORD_TOKEN in your shell."
        )

    return Settings(
        discord_token=token,
        guild_id=_int_or_none(os.getenv("GUILD_ID")),
        jikan_base_url=os.getenv("JIKAN_BASE_URL", "https://api.jikan.moe/v4"),
        rate_limit_per_second=_float_env("JIKAN_RATE_LIMIT_PER_SECOND", 3.0),
        rate_limit_per_minute=_int_env("JIKAN_RATE_LIMIT_PER_MINUTE", 60),
        max_retries=_int_env("JIKAN_MAX_RETRIES", 3),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached, process-wide Settings instance (loaded on first access)."""
    return load_settings()



settings = load_settings()

