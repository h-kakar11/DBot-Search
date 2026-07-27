"""Entry point for mal-search-bot.

Creates the Discord bot with no privileged intents (slash-commands only),
initializes the shared Jikan API client, registers the /anime, /manga, and
/movie slash commands, syncs them (to a dev guild if configured, otherwise
globally), and cleanly tears down the Jikan client's HTTP session on shutdown.
"""
from __future__ import annotations

import asyncio
import logging
import sys

import discord
from discord.ext import commands

from commands.anime import anime_command
from commands.manga import manga_command
from commands.movie import movie_command
from config import ConfigError, Settings, get_settings
from services.jikan_client import JikanClient

logger = logging.getLogger("mal_search_bot.bot")


def _configure_logging(level_name: str) -> None:
    """Configure root logging for startup, command usage, and API error visibility."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


class MalSearchBot(commands.Bot):
    """The mal-search-bot Discord client: slash-commands only, no privileged intents."""

    def __init__(self, settings: Settings) -> None:
        """Configure intents and construct the shared Jikan API client."""
        # No privileged intents needed: this bot only responds to slash commands.
        intents = discord.Intents.default()
        intents.message_content = False
        intents.members = False

        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

        self.settings = settings
        self.jikan_client = JikanClient(
            base_url=settings.jikan_base_url,
            rate_limit_per_second=settings.rate_limit_per_second,
            rate_limit_per_minute=settings.rate_limit_per_minute,
            max_retries=settings.max_retries,
        )

    async def setup_hook(self) -> None:
        """Start the Jikan HTTP session, register commands, and sync the command tree."""
        await self.jikan_client.start()

        self.tree.add_command(anime_command)
        self.tree.add_command(manga_command)
        self.tree.add_command(movie_command)

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d command(s) to guild %s", len(synced), self.settings.guild_id)
        else:
            synced = await self.tree.sync()
            logger.info("Synced %d command(s) globally", len(synced))

    async def close(self) -> None:
        """Close the Jikan HTTP session before shutting down the Discord connection."""
        await self.jikan_client.close()
        await super().close()


async def main() -> None:
    """Load settings, configure logging, and run the bot until interrupted."""
    try:
        settings = get_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    _configure_logging(settings.log_level)

    bot = MalSearchBot(settings)

    @bot.event
    async def on_ready() -> None:
        logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id if bot.user else "?")
        logger.info("Connected to %d guild(s)", len(bot.guilds))

    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down (KeyboardInterrupt).")
