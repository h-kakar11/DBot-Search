"""Configuration loading for mal-search-bot.

Secrets (the bot token) can come from either a `.env` file (`DISCORD_TOKEN`)
or a `token.yaml` file (`token:` key). Non-secret settings live in
`config.yaml` and can be overridden with matching UPPER_CASE environment
variables (see `.env.example`).
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_token_data = _load_yaml(BASE_DIR / "token.yaml")
_config_data = _load_yaml(BASE_DIR / "config.yaml")


def _int_or_none(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --- Secret: bot token ------------------------------------------------
TOKEN: Optional[str] = os.getenv("DISCORD_TOKEN") or _token_data.get("token")

# --- Optional: guild id for fast (instant) slash command sync during dev
GUILD_ID: Optional[int] = _int_or_none(os.getenv("GUILD_ID")) or _int_or_none(
    _config_data.get("guild_id")
)

# --- Notification channels ---------------------------------------------
NOTIFY_CHANNEL_ID: Optional[int] = _int_or_none(os.getenv("NOTIFY_CHANNEL_ID")) or _int_or_none(
    _config_data.get("notify_channel_id")
)
NOTIFY_CHANNEL_NAME: Optional[str] = os.getenv("NOTIFY_CHANNEL_NAME") or _config_data.get(
    "notify_channel_name", "anime-announcements"
)

RELEASE_CHANNEL_ID: Optional[int] = _int_or_none(os.getenv("RELEASE_CHANNEL_ID")) or _int_or_none(
    _config_data.get("release_channel_id")
)
RELEASE_CHANNEL_NAME: Optional[str] = os.getenv("RELEASE_CHANNEL_NAME") or _config_data.get(
    "release_channel_name"
)

# --- Poll intervals (hours) ---------------------------------------------
UPCOMING_POLL_INTERVAL_HOURS: float = float(
    os.getenv("UPCOMING_POLL_INTERVAL_HOURS") or _config_data.get("upcoming_poll_interval_hours", 6)
)
RELEASE_POLL_INTERVAL_HOURS: float = float(
    os.getenv("RELEASE_POLL_INTERVAL_HOURS") or _config_data.get("release_poll_interval_hours", 24)
)
