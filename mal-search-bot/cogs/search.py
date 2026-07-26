"""Slash commands for searching MyAnimeList content via the Jikan API."""
from __future__ import annotations

import logging
from typing import Any, Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from embeds import build_anime_embed, build_manga_embed, get_english_title
from jikan_client import JikanAPIError

logger = logging.getLogger("mal_search_bot.search")

Season = Literal["winter", "spring", "summer", "fall"]

MAX_EXTRA_RESULTS = 5
DISAMBIGUATION_TIMEOUT = 60.0


def _all_titles(entry: dict[str, Any]) -> list[str]:
    """Collect every title string associated with a result entry."""
    titles = [t.get("title", "") for t in (entry.get("titles") or [])]
    if entry.get("title"):
        titles.append(entry["title"])
    return [t for t in titles if t]


def _matches_name(entry: dict[str, Any], name: str) -> bool:
    needle = name.lower()
    return any(needle in title.lower() for title in _all_titles(entry))


def _aired_year(entry: dict[str, Any]) -> Optional[int]:
    if entry.get("year"):
        return entry["year"]
    aired = entry.get("aired") or {}
    prop = aired.get("prop") or {}
    from_date = prop.get("from") or {}
    return from_date.get("year")


class ResultSelect(discord.ui.Select):
    """A select menu letting the user switch between multiple search matches."""

    def __init__(self, results: list[dict[str, Any]], embed_builder):
        self._results = results
        self._embed_builder = embed_builder

        options = []
        for i, entry in enumerate(results):
            label = get_english_title(entry)[:100]
            options.append(discord.SelectOption(label=label, value=str(i)))

        super().__init__(
            placeholder="Show a different match...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        index = int(self.values[0])
        data = self._results[index]
        embed = self._embed_builder(data)
        await interaction.response.edit_message(embed=embed, view=self.view)


class DisambiguationView(discord.ui.View):
    """View holding the disambiguation select menu; disables itself after a timeout."""

    def __init__(self, results: list[dict[str, Any]], embed_builder, timeout: float = DISAMBIGUATION_TIMEOUT):
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        self.add_item(ResultSelect(results, embed_builder))

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class SearchCog(commands.Cog):
    """Slash commands for /anime, /manga, and /movie searches."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def jikan(self):
        return self.bot.jikan_client

    async def _send_disambiguated(
        self,
        interaction: discord.Interaction,
        primary: dict[str, Any],
        extras: list[dict[str, Any]],
        embed_builder,
        note: Optional[str] = None,
    ) -> None:
        embed = embed_builder(primary, note=note) if note else embed_builder(primary)

        view: Optional[DisambiguationView] = None
        if extras:
            count = len(extras)
            plural = "es" if count != 1 else ""
            dropdown_note = f"{count} other match{plural} found — use the dropdown below."
            existing_footer = embed.footer.text if embed.footer else None
            combined = f"{existing_footer} | {dropdown_note}" if existing_footer else dropdown_note
            embed.set_footer(text=combined)
            view = DisambiguationView(extras, embed_builder)

        if view is not None:
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message
        else:
            await interaction.followup.send(embed=embed)

    async def _handle_error(self, interaction: discord.Interaction, kind: str, exc: JikanAPIError) -> None:
        logger.error("Jikan API error while searching %s: %s", kind, exc)
        await interaction.followup.send(
            "Sorry, something went wrong while talking to MyAnimeList (Jikan API). "
            "Please try again in a moment.",
            ephemeral=True,
        )

    @app_commands.command(name="anime", description="Search for an anime on MyAnimeList")
    @app_commands.describe(
        name="The anime name to search for",
        season="Optional: filter/search by season (requires year too for seasonal lookup)",
        year="Optional: filter/search by year aired",
    )
    async def anime(
        self,
        interaction: discord.Interaction,
        name: str,
        season: Optional[Season] = None,
        year: Optional[int] = None,
    ) -> None:
        await interaction.response.defer()

        try:
            if season and year:
                candidates = await self.jikan.get_seasonal(year, season)
                results = [c for c in candidates if _matches_name(c, name)]
            elif year:
                candidates = await self.jikan.search_anime(name, limit=10)
                results = [c for c in candidates if _aired_year(c) == year]
            else:
                results = await self.jikan.search_anime(name, limit=10)
        except JikanAPIError as exc:
            await self._handle_error(interaction, "anime", exc)
            return

        if not results:
            await interaction.followup.send(
                f"No anime found matching '{name}'. Try checking the spelling or being more specific.",
                ephemeral=True,
            )
            return

        primary, extras = results[0], results[1 : 1 + MAX_EXTRA_RESULTS]
        await self._send_disambiguated(interaction, primary, extras, build_anime_embed)

    @app_commands.command(name="manga", description="Search for a manga on MyAnimeList")
    @app_commands.describe(name="The manga name to search for")
    async def manga(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer()

        try:
            results = await self.jikan.search_manga(name, limit=10)
        except JikanAPIError as exc:
            await self._handle_error(interaction, "manga", exc)
            return

        if not results:
            await interaction.followup.send(
                f"No manga found matching '{name}'. Try checking the spelling or being more specific.",
                ephemeral=True,
            )
            return

        primary, extras = results[0], results[1 : 1 + MAX_EXTRA_RESULTS]
        await self._send_disambiguated(interaction, primary, extras, build_manga_embed)

    @app_commands.command(name="movie", description="Search for an anime movie on MyAnimeList")
    @app_commands.describe(name="The movie name to search for")
    async def movie(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer()

        try:
            results = await self.jikan.search_anime(name, limit=10)
        except JikanAPIError as exc:
            await self._handle_error(interaction, "movie", exc)
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

        await self._send_disambiguated(interaction, primary, extras, build_anime_embed, note=note)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SearchCog(bot))
