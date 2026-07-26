"""`/anime` slash command: search MyAnimeList anime entries via Jikan."""
from __future__ import annotations

import logging
from typing import Any, Literal, Optional, TYPE_CHECKING

import discord
from discord import app_commands

from services.jikan_client import JikanAPIError
from ui.result_select import MAX_EXTRA_RESULTS, send_result_with_dropdown
from utils.embed_builder import build_anime_embed

if TYPE_CHECKING:
    from bot import MalSearchBot

logger = logging.getLogger("mal_search_bot.commands.anime")

Season = Literal["winter", "spring", "summer", "fall"]


def _all_titles(entry: dict[str, Any]) -> list[str]:
    """Collect every title string associated with a result entry."""
    titles = [t.get("title", "") for t in (entry.get("titles") or [])]
    if entry.get("title"):
        titles.append(entry["title"])
    return [t for t in titles if t]


def _matches_name(entry: dict[str, Any], name: str) -> bool:
    """Return True if `name` is a case-insensitive substring of any title."""
    needle = name.lower()
    return any(needle in title.lower() for title in _all_titles(entry))


def _aired_year(entry: dict[str, Any]) -> Optional[int]:
    """Best-effort extraction of the year an anime aired, from various Jikan fields."""
    if entry.get("year"):
        return entry["year"]
    aired = entry.get("aired") or {}
    prop = aired.get("prop") or {}
    from_date = prop.get("from") or {}
    return from_date.get("year")


@app_commands.command(name="anime", description="Search for an anime on MyAnimeList")
@app_commands.describe(
    name="The anime name to search for",
    season="Optional: season to narrow the search (pair with year for a seasonal lookup)",
    year="Optional: year aired to narrow the search",
)
async def anime_command(
    interaction: discord.Interaction,
    name: str,
    season: Optional[Season] = None,
    year: Optional[int] = None,
) -> None:
    """Search Jikan for an anime by name, optionally narrowed by season/year.

    If both `season` and `year` are given, uses Jikan's seasonal endpoint and
    matches results by case-insensitive substring against `name`. If only
    `year` is given, filters plain search results by aired year.
    """
    logger.info(
        "/anime invoked by %s (guild=%s): name=%r season=%r year=%r",
        interaction.user,
        interaction.guild_id,
        name,
        season,
        year,
    )

    try:
        await interaction.response.defer()
    except discord.InteractionResponded:
        pass
    except discord.HTTPException:
        logger.exception("Failed to defer /anime interaction; aborting.")
        return

    client = interaction.client.jikan_client  # type: MalSearchBot's JikanClient

    try:
        if season and year:
            candidates = await client.get_seasonal(year, season)
            results = [c for c in candidates if _matches_name(c, name)]
        elif year:
            candidates = await client.search_anime(name, limit=10)
            results = [c for c in candidates if _aired_year(c) == year]
        else:
            results = await client.search_anime(name, limit=10)
    except JikanAPIError:
        logger.exception("Jikan API error while searching anime %r", name)
        await interaction.followup.send(
            "Sorry, something went wrong while talking to MyAnimeList (Jikan API). "
            "Please try again in a moment.",
            ephemeral=True,
        )
        return

    if not results:
        await interaction.followup.send(
            f"No anime found matching '{name}'. Try checking the spelling or being more specific.",
            ephemeral=True,
        )
        return

    primary, extras = results[0], results[1 : 1 + MAX_EXTRA_RESULTS]
    await send_result_with_dropdown(interaction, primary, extras, build_anime_embed)
