"""Entry point for mal-search-bot.

Sets up the discord.py bot, registers cogs (search + notifications), and
syncs slash commands on startup. This bot only uses slash commands, so no
privileged intents (message content, members, presences) are required.
"""

import logging

import discord
from discord.ext import commands

import config
from cogs.notifications import NotificationsCog
from cogs.search import SearchCog
from jikan_client import JikanClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mal_search_bot")

intents = discord.Intents.default()
intents.message_content = False


class MalSearchBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.jikan = JikanClient()

    async def setup_hook(self):
        await self.jikan.start()
        await self.add_cog(SearchCog(self, self.jikan))
        await self.add_cog(NotificationsCog(self, self.jikan))

        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced application commands to guild %s", config.GUILD_ID)
        else:
            await self.tree.sync()
            logger.info("Synced global application commands (may take up to an hour to propagate)")

    async def close(self):
        await self.jikan.close()
        await super().close()

    async def on_ready(self):
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "?")


def main():
    if not config.TOKEN:
        raise SystemExit(
            "No Discord bot token found. Set DISCORD_TOKEN in a .env file, "
            "or 'token' in token.yaml (see .env.example / token.yaml.example)."
        )
    bot = MalSearchBot()
    bot.run(config.TOKEN)


if __name__ == "__main__":
    main()
