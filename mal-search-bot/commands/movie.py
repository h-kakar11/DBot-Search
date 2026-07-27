"""`/movie` slash command: search MyAnimeList anime movies via Jikan."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from services.jikan_client import JikanAPIError
from ui.result_select import MAX_EXTRA_RESULTS, send_result_with_dropdown
from utils.embed_builder import build_anime_embed

if TYPE_CHECKING:
    from bot import MalSearchBot

logger = logging.getLogger("mal_search_bot.commands.movie")


@app_commands.command(name="movie", description="Search for an anime movie on MyAnimeList")
@app_commands.describe(name="The movie name to search for")
async def movie_command(interaction: discord.Interaction, name: str) -> None:
    """Search Jikan's anime search for a movie-type entry matching `name`.

    Falls back to the closest overall anime match (with a note in the embed)
    if no result has `type == "Movie"`.
    """
    logger.info("/movie invoked by %s (guild=%s): name=%r", interaction.user, interaction.guild_id, name)

    try:
        await interaction.response.defer()
    except discord.InteractionResponded:
        pass
    except discord.HTTPException:
        logger.exception("Failed to defer /movie interaction; aborting.")
        return

    client = interaction.client.jikan_client  # type: MalSearchBot's JikanClient

    try:
        results = await client.search_anime(name, limit=10)
    except JikanAPIError:
        logger.exception("Jikan API error while searching movie %r", name)
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

    movie_matches = [r for r in results if r.get("type") == "Movie"]

    if movie_matches:
        primary, extras = movie_matches[0], movie_matches[1 : 1 + MAX_EXTRA_RESULTS]
        note = None
    else:
        primary, extras = results[0], results[1 : 1 + MAX_EXTRA_RESULTS]
        note = "No movie match was found — showing the closest anime match instead."

    await send_result_with_dropdown(interaction, primary, extras, build_anime_embed, note=note)
