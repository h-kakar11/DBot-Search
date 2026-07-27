"""Slash commands for searching MyAnimeList content via Jikan: /anime, /manga, /movie."""

import logging
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from embeds import build_anime_embed, build_manga_embed, get_display_title
from jikan_client import JikanAPIError, JikanClient

logger = logging.getLogger(__name__)

Season = Literal["winter", "spring", "summer", "fall"]

JIKAN_ERROR_MESSAGE = (
    "Couldn't reach the Jikan API (MyAnimeList data source) right now. "
    "Please try again in a moment."
)


class ResultSelect(discord.ui.Select):
    """Dropdown letting the user pick a different match from the search results."""

    def __init__(self, entries: list, build_embed):
        self._entries = {str(e["mal_id"]): e for e in entries}
        self._build_embed = build_embed
        options = [
            discord.SelectOption(
                label=get_display_title(e)[:100],
                description=f"MAL ID: {e.get('mal_id')} • {e.get('type') or 'Unknown type'}",
                value=str(e["mal_id"]),
            )
            for e in entries
        ]
        super().__init__(placeholder="Other matching results...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        entry = self._entries.get(self.values[0])
        if entry is None:
            await interaction.response.send_message("That result is no longer available.", ephemeral=True)
            return
        embed = self._build_embed(entry)
        await interaction.response.edit_message(embed=embed, view=None)


class ResultView(discord.ui.View):
    """View holding the disambiguation dropdown, with graceful timeout handling."""

    def __init__(self, entries: list, build_embed, timeout: float = 90):
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        if entries:
            self.add_item(ResultSelect(entries, build_embed))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot, jikan: JikanClient):
        self.bot = bot
        self.jikan = jikan

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        logger.exception("Unhandled error in search command", exc_info=error)
        message = "Something went wrong running that command. Please try again later."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def _send_results(
        self, interaction: discord.Interaction, entries: list, query: str, build_embed
    ) -> None:
        if not entries:
            await interaction.followup.send(
                f"No anime found matching '{query}'. Try checking the spelling or being more specific.",
                ephemeral=True,
            )
            return

        top, others = entries[0], entries[1:6]
        note = f"🔎 {len(others)} other result(s) found — pick one below to switch." if others else None
        embed = build_embed(top, note=note)
        view = ResultView(others, build_embed) if others else None
        message = await interaction.followup.send(embed=embed, view=view)
        if view is not None:
            view.message = message

    @app_commands.command(name="anime", description="Search for an anime on MyAnimeList")
    @app_commands.describe(
        name="Anime title to search for",
        season="Filter to a specific anime season",
        year="Filter to a specific year (e.g. 2023)",
    )
    async def anime(
        self,
        interaction: discord.Interaction,
        name: str,
        season: Optional[Season] = None,
        year: Optional[app_commands.Range[int, 1900, 2100]] = None,
    ):
        await interaction.response.defer()
        try:
            if season and year:
                entries = await self.jikan.get_season(year, season)
                needle = name.lower()
                entries = [
                    e
                    for e in entries
                    if needle in get_display_title(e).lower() or needle in (e.get("title") or "").lower()
                ]
            else:
                entries = await self.jikan.search_anime(name, limit=15)
                if year:
                    filtered = [e for e in entries if e.get("year") == year]
                    if filtered:
                        entries = filtered
        except JikanAPIError:
            await interaction.followup.send(JIKAN_ERROR_MESSAGE, ephemeral=True)
            return

        await self._send_results(interaction, entries, name, build_anime_embed)

    @app_commands.command(name="manga", description="Search for a manga on MyAnimeList")
    @app_commands.describe(name="Manga title to search for")
    async def manga(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            entries = await self.jikan.search_manga(name, limit=15)
        except JikanAPIError:
            await interaction.followup.send(JIKAN_ERROR_MESSAGE, ephemeral=True)
            return

        if not entries:
            await interaction.followup.send(
                f"No manga found matching '{name}'. Try checking the spelling or being more specific.",
                ephemeral=True,
            )
            return

        await self._send_results(interaction, entries, name, build_manga_embed)

    @app_commands.command(name="movie", description="Search for an anime movie on MyAnimeList")
    @app_commands.describe(name="Movie title to search for")
    async def movie(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            entries = await self.jikan.search_anime(name, limit=15)
        except JikanAPIError:
            await interaction.followup.send(JIKAN_ERROR_MESSAGE, ephemeral=True)
            return

        if not entries:
            await interaction.followup.send(
                f"No anime found matching '{name}'. Try checking the spelling or being more specific.",
                ephemeral=True,
            )
            return

        movies = [e for e in entries if (e.get("type") or "").lower() == "movie"]
        if movies:
            top, others = movies[0], movies[1:6]
            note = f"🔎 {len(others)} other movie result(s) found — pick one below to switch." if others else None
        else:
            top, others = entries[0], entries[1:6]
            note = "⚠️ No exact movie match found — showing the closest anime match instead."

        embed = build_anime_embed(top, note=note)
        view = ResultView(others, build_anime_embed) if others else None
        message = await interaction.followup.send(embed=embed, view=view)
        if view is not None:
            view.message = message


async def setup(bot: commands.Bot):
    # Not used directly (cogs are constructed with a shared JikanClient in
    # bot.py's setup_hook), but kept for compatibility with `bot.load_extension`.
    await bot.add_cog(SearchCog(bot, bot.jikan))
