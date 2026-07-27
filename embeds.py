"""Helpers for turning Jikan API entries into Discord embeds."""

from typing import Optional

import discord


def get_display_title(entry: dict) -> str:
    """Prefer the English title, falling back to the canonical/romaji title."""
    for t in entry.get("titles") or []:
        if t.get("type") == "English" and t.get("title"):
            return t["title"]
    if entry.get("title_english"):
        return entry["title_english"]
    return entry.get("title") or "Unknown Title"


def truncate(text: Optional[str], length: int = 300) -> str:
    if not text:
        return "No synopsis available."
    text = text.strip()
    if len(text) <= length:
        return text
    return text[:length].rstrip() + "..."


def _score_text(entry: dict) -> str:
    score = entry.get("score")
    scored_by = entry.get("scored_by")
    if not score:
        return "N/A"
    text = f"⭐ {score}"
    if scored_by:
        text += f" ({scored_by:,} votes)"
    return text


def _genres_text(entry: dict) -> str:
    genres = entry.get("genres") or []
    if not genres:
        return "N/A"
    return ", ".join(g["name"] for g in genres)


def _image_url(entry: dict) -> Optional[str]:
    return (entry.get("images") or {}).get("jpg", {}).get("large_image_url")


def build_anime_embed(entry: dict, note: Optional[str] = None) -> discord.Embed:
    embed = discord.Embed(
        title=get_display_title(entry),
        url=entry.get("url"),
        description=truncate(entry.get("synopsis")),
        color=discord.Color.blue(),
    )
    embed.add_field(name="Score", value=_score_text(entry), inline=True)
    embed.add_field(name="Status", value=entry.get("status") or "Unknown", inline=True)
    embed.add_field(name="Episodes", value=str(entry.get("episodes") or "?"), inline=True)

    season, year = entry.get("season"), entry.get("year")
    if season and year:
        aired_text = f"{season.capitalize()} {year}"
    elif year:
        aired_text = str(year)
    else:
        aired_text = "Unknown"
    embed.add_field(name="Season/Year", value=aired_text, inline=True)
    embed.add_field(name="Genres", value=_genres_text(entry), inline=False)

    image_url = _image_url(entry)
    if image_url:
        embed.set_image(url=image_url)
    if note:
        embed.set_footer(text=note)
    return embed


def build_manga_embed(entry: dict, note: Optional[str] = None) -> discord.Embed:
    embed = discord.Embed(
        title=get_display_title(entry),
        url=entry.get("url"),
        description=truncate(entry.get("synopsis")),
        color=discord.Color.green(),
    )
    embed.add_field(name="Score", value=_score_text(entry), inline=True)
    embed.add_field(name="Status", value=entry.get("status") or "Unknown", inline=True)
    volumes = entry.get("volumes") or "?"
    chapters = entry.get("chapters") or "?"
    embed.add_field(name="Volumes / Chapters", value=f"{volumes} / {chapters}", inline=True)
    embed.add_field(name="Genres", value=_genres_text(entry), inline=False)

    image_url = _image_url(entry)
    if image_url:
        embed.set_image(url=image_url)
    if note:
        embed.set_footer(text=note)
    return embed
