"""Embed builders for anime/manga search results, plus shared formatting helpers."""
from __future__ import annotations

from typing import Any, Optional

import discord

SYNOPSIS_MAX_LENGTH = 300


def get_english_title(data: dict[str, Any]) -> str:
    """Return the English title from the `titles` array, falling back to the
    default/canonical title if no English title exists."""
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
    """Format the genres (plus explicit_genres/themes/demographics if present)
    list into a comma-separated string."""
    genres = data.get("genres") or []
    names = [g.get("name") for g in genres if g.get("name")]
    if not names:
        return "N/A"
    return ", ".join(names)


def truncate_synopsis(synopsis: Optional[str], max_length: int = SYNOPSIS_MAX_LENGTH) -> str:
    """Truncate a synopsis to roughly max_length characters, appending '...'."""
    if not synopsis:
        return "No synopsis available."
    synopsis = synopsis.strip()
    if len(synopsis) <= max_length:
        return synopsis
    return synopsis[:max_length].rstrip() + "..."


def get_cover_image(data: dict[str, Any]) -> Optional[str]:
    images = data.get("images") or {}
    jpg = images.get("jpg") or {}
    return jpg.get("large_image_url") or jpg.get("image_url")


def build_anime_embed(data: dict[str, Any], note: Optional[str] = None) -> discord.Embed:
    """Build a Discord embed for an anime search result."""
    title = get_english_title(data)
    url = data.get("url")

    embed = discord.Embed(title=title, url=url, color=discord.Color.blue())

    score = data.get("score")
    scored_by = data.get("scored_by")
    if score is not None:
        score_text = f"{score}"
        if scored_by:
            score_text += f" ({scored_by:,} votes)"
    else:
        score_text = "N/A"
    embed.add_field(name="Score", value=score_text, inline=True)

    status = data.get("status") or "Unknown"
    embed.add_field(name="Status", value=status, inline=True)

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
    embed.add_field(name="Synopsis", value=truncate_synopsis(data.get("synopsis")), inline=False)

    image_url = get_cover_image(data)
    if image_url:
        embed.set_image(url=image_url)

    if note:
        embed.set_footer(text=note)

    return embed


def build_manga_embed(data: dict[str, Any], note: Optional[str] = None) -> discord.Embed:
    """Build a Discord embed for a manga search result."""
    title = get_english_title(data)
    url = data.get("url")

    embed = discord.Embed(title=title, url=url, color=discord.Color.green())

    score = data.get("score")
    scored_by = data.get("scored_by")
    if score is not None:
        score_text = f"{score}"
        if scored_by:
            score_text += f" ({scored_by:,} votes)"
    else:
        score_text = "N/A"
    embed.add_field(name="Score", value=score_text, inline=True)

    status = data.get("status") or "Unknown"
    embed.add_field(name="Status", value=status, inline=True)

    volumes = data.get("volumes")
    chapters = data.get("chapters")
    embed.add_field(
        name="Volumes", value=str(volumes) if volumes is not None else "N/A", inline=True
    )
    embed.add_field(
        name="Chapters", value=str(chapters) if chapters is not None else "N/A", inline=True
    )

    embed.add_field(name="Genres", value=format_genres(data), inline=False)
    embed.add_field(name="Synopsis", value=truncate_synopsis(data.get("synopsis")), inline=False)

    image_url = get_cover_image(data)
    if image_url:
        embed.set_image(url=image_url)

    if note:
        embed.set_footer(text=note)

    return embed
