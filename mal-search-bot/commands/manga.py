"""`/manga` slash command: search MyAnimeList manga entries via Jikan."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from services.jikan_client import JikanAPIError
from ui.result_select import MAX_EXTRA_RESULTS, send_result_with_dropdown
from utils.embed_builder import build_manga_embed

if TYPE_CHECKING:
    from bot import MalSearchBot

logger = logging.getLogger("mal_search_bot.commands.manga")


@app_commands.command(name="manga", description="Search for a manga on MyAnimeList")
@app_commands.describe(name="The manga name to search for")
async def manga_command(interaction: discord.Interaction, name: str) -> None:
    """Search Jikan for a manga by name and reply with an embed (plus disambiguation)."""
    logger.info("/manga invoked by %s (guild=%s): name=%r", interaction.user, interaction.guild_id, name)

    try:
        await interaction.response.defer()
    except discord.InteractionResponded:
        pass
    except discord.HTTPException:
        logger.exception("Failed to defer /manga interaction; aborting.")
        return

    client = interaction.client.jikan_client  # type: MalSearchBot's JikanClient

    try:
        results = await client.search_manga(name, limit=10)
    except JikanAPIError:
        logger.exception("Jikan API error while searching manga %r", name)
        await interaction.followup.send(
            "Sorry, something went wrong while talking to MyAnimeList (Jikan API). "
            "Please try again in a moment.",
            ephemeral=True,
        )
        return

    if not results:
        await interaction.followup.send(
            f"No manga found matching '{name}'. Try checking the spelling or being more specific.",
            ephemeral=True,
        )
        return

    primary, extras = results[0], results[1 : 1 + MAX_EXTRA_RESULTS]
    await send_result_with_dropdown(interaction, primary, extras, build_manga_embed)
