"""Entry point for mal-search-bot.

Creates the Discord bot with no privileged intents (slash-commands only),
initializes the shared Jikan API client, loads the search cog, syncs slash
commands (to a dev guild if configured, otherwise globally), and cleanly
tears down the Jikan client's HTTP session on shutdown.
"""
from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from config import config, get_token
from jikan_client import JikanClient

logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("mal_search_bot.bot")


class MalSearchBot(commands.Bot):
    def __init__(self) -> None:
        # No privileged intents needed: this bot is slash-commands only.
        intents = discord.Intents.default()
        intents.message_content = False
        intents.members = False

        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

        self.jikan_client = JikanClient(
            base_url=config.jikan_base_url,
            rate_limit_per_second=config.rate_limit_per_second,
            rate_limit_per_minute=config.rate_limit_per_minute,
            max_retries=config.max_retries,
        )

    async def setup_hook(self) -> None:
        await self.jikan_client.start()
        await self.load_extension("cogs.search")

        if config.guild_id:
            guild = discord.Object(id=config.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d command(s) to guild %s", len(synced), config.guild_id)
        else:
            synced = await self.tree.sync()
            logger.info("Synced %d command(s) globally", len(synced))

    async def close(self) -> None:
        await self.jikan_client.close()
        await super().close()


async def main() -> None:
    bot = MalSearchBot()

    @bot.event
    async def on_ready():
        logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id if bot.user else "?")

    token = get_token()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
