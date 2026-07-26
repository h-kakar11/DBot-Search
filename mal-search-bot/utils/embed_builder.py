"""Embed builders for anime/manga search results, plus shared formatting helpers.

All builders respect Discord's embed field-length limits (256 chars for
field names/titles, 1024 chars for field values) to avoid HTTP 400s from the
Discord API on unusually long MAL data.
"""
from __future__ import annotations

from typing import Any, Optional

import discord

SYNOPSIS_MAX_LENGTH = 300
EMBED_TITLE_MAX_LENGTH = 256
EMBED_FIELD_VALUE_MAX_LENGTH = 1024


def get_english_title(data: dict[str, Any]) -> str:
    """Return the English title from the `titles` array.

    Falls back to the default/canonical `title` field if no entry with
    `type == "English"` exists, and finally to a generic placeholder.
    """
    titles = data.get("titles") or []
    for entry in titles:
        if entry.get("type") == "English" and entry.get("title"):
            return entry["title"]

    fallback = data.get("title")
    if fallback:
        return fallback

    for entry in titles:
        if entry.get("type") == "Default" and entry.get("title"):
            return entry["title"]

    return "Unknown Title"


def format_genres(data: dict[str, Any]) -> str:
    """Format the `genres` list into a comma-separated string, or "N/A" if empty."""
    genres = data.get("genres") or []
    names = [g.get("name") for g in genres if g.get("name")]
    if not names:
        return "N/A"
    return _truncate(", ".join(names), EMBED_FIELD_VALUE_MAX_LENGTH)


def truncate_synopsis(synopsis: Optional[str], max_length: int = SYNOPSIS_MAX_LENGTH) -> str:
    """Truncate a synopsis to roughly `max_length` characters, appending '...'."""
    if not synopsis:
        return "No synopsis available."
    synopsis = synopsis.strip()
    if len(synopsis) <= max_length:
        return synopsis
    return synopsis[:max_length].rstrip() + "..."


def _truncate(text: str, max_length: int) -> str:
    """Hard-truncate arbitrary text to fit within a Discord embed field limit."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def get_cover_image(data: dict[str, Any]) -> Optional[str]:
    """Return the best available cover image URL, preferring the large JPG variant."""
    images = data.get("images") or {}
    jpg = images.get("jpg") or {}
    return jpg.get("large_image_url") or jpg.get("image_url")


def _score_text(data: dict[str, Any]) -> str:
    """Format the MAL score and vote count into a display string."""
    score = data.get("score")
    scored_by = data.get("scored_by")
    if score is None:
        return "N/A"
    text = f"{score}"
    if scored_by:
        text += f" ({scored_by:,} votes)"
    return text


def build_anime_embed(data: dict[str, Any], note: Optional[str] = None) -> discord.Embed:
    """Build a Discord embed summarizing an anime search result.

    Args:
        data: A raw Jikan anime entry (from a search or seasonal endpoint).
        note: Optional footer note, e.g. to flag a fallback/disambiguation hint.

    Returns:
        A populated `discord.Embed` with title, score, status, episodes,
        season/year, genres, synopsis, and cover image.
    """
    title = _truncate(get_english_title(data), EMBED_TITLE_MAX_LENGTH)
    url = data.get("url")

    embed = discord.Embed(title=title, url=url, color=discord.Color.blue())
    embed.add_field(name="Score", value=_score_text(data), inline=True)
    embed.add_field(name="Status", value=data.get("status") or "Unknown", inline=True)

    episodes = data.get("episodes")
    embed.add_field(
        name="Episodes", value=str(episodes) if episodes is not None else "N/A", inline=True
    )

    season = data.get("season")
    year = data.get("year")
    if season and year:
        aired_text = f"{season.capitalize()} {year}"
    elif year:
        aired_text = str(year)
    else:
        aired_text = "N/A"
    embed.add_field(name="Season/Year", value=aired_text, inline=True)

    embed.add_field(name="Genres", value=format_genres(data), inline=False)
    embed.add_field(
        name="Synopsis",
        value=_truncate(truncate_synopsis(data.get("synopsis")), EMBED_FIELD_VALUE_MAX_LENGTH),
        inline=False,
    )

    image_url = get_cover_image(data)
    if image_url:
        embed.set_image(url=image_url)

    if note:
        embed.set_footer(text=_truncate(note, 2048))

    return embed


def build_manga_embed(data: dict[str, Any], note: Optional[str] = None) -> discord.Embed:
    """Build a Discord embed summarizing a manga search result.

    Args:
        data: A raw Jikan manga entry (from the manga search endpoint).
        note: Optional footer note, e.g. to flag a fallback/disambiguation hint.

    Returns:
        A populated `discord.Embed` with title, score, status, volume/chapter
        counts, genres, synopsis, and cover image.
    """
    title = _truncate(get_english_title(data), EMBED_TITLE_MAX_LENGTH)
    url = data.get("url")

    embed = discord.Embed(title=title, url=url, color=discord.Color.green())
    embed.add_field(name="Score", value=_score_text(data), inline=True)
    embed.add_field(name="Status", value=data.get("status") or "Unknown", inline=True)

    volumes = data.get("volumes")
    chapters = data.get("chapters")
    embed.add_field(
        name="Volumes", value=str(volumes) if volumes is not None else "N/A", inline=True
    )
    embed.add_field(
        name="Chapters", value=str(chapters) if chapters is not None else "N/A", inline=True
    )

    embed.add_field(name="Genres", value=format_genres(data), inline=False)
    embed.add_field(
        name="Synopsis",
        value=_truncate(truncate_synopsis(data.get("synopsis")), EMBED_FIELD_VALUE_MAX_LENGTH),
        inline=False,
    )

    image_url = get_cover_image(data)
    if image_url:
        embed.set_image(url=image_url)

    if note:
        embed.set_footer(text=_truncate(note, 2048))

    return embed
