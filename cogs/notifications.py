"""Background notification loops: newly announced/upcoming anime, and
release/new-episode notifications for a watchlist of currently-airing anime.

Both loops use discord.py's `tasks.loop` for lifecycle management (start/stop
tied to the cog, automatic `before_loop` wait-until-ready) rather than raw
`asyncio.sleep` loops.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import storage
from embeds import build_anime_embed, get_display_title
from jikan_client import JikanAPIError, JikanClient, JikanNotFoundError

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SEEN_UPCOMING_FILE = BASE_DIR / "seen_upcoming.json"
WATCHLIST_FILE = BASE_DIR / "watchlist.json"
RELEASE_STATE_FILE = BASE_DIR / "release_state.json"

WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def resolve_channel(bot: commands.Bot, channel_id, channel_name):
    """Find a text channel by id first, then by name across every guild the bot is in."""
    if channel_id:
        channel = bot.get_channel(int(channel_id))
        if channel:
            return channel
    if channel_name:
        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                return channel
    return None


class NotificationsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, jikan: JikanClient):
        self.bot = bot
        self.jikan = jikan
        self.seen_upcoming: set = set(storage.load_json(SEEN_UPCOMING_FILE, []))
        self.watchlist: set = set(str(i) for i in storage.load_json(WATCHLIST_FILE, []))
        self.release_state: dict = storage.load_json(RELEASE_STATE_FILE, {})

        self.upcoming_loop.change_interval(hours=config.UPCOMING_POLL_INTERVAL_HOURS)
        self.release_loop.change_interval(hours=config.RELEASE_POLL_INTERVAL_HOURS)
        self.upcoming_loop.start()
        self.release_loop.start()

    def cog_unload(self):
        self.upcoming_loop.cancel()
        self.release_loop.cancel()

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "You need the **Manage Server** permission to use this command."
        else:
            logger.exception("Unhandled error in notifications command", exc_info=error)
            message = "Something went wrong running that command. Please try again later."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # --- Loop 1: newly announced / upcoming anime -------------------------

    @tasks.loop(hours=6)
    async def upcoming_loop(self):
        channel = resolve_channel(self.bot, config.NOTIFY_CHANNEL_ID, config.NOTIFY_CHANNEL_NAME)
        if not channel:
            logger.warning(
                "Upcoming-anime notify channel not found; check NOTIFY_CHANNEL_ID / NOTIFY_CHANNEL_NAME."
            )
            return

        try:
            entries = await self.jikan.get_upcoming(max_pages=3)
        except JikanAPIError:
            logger.exception("Failed to fetch upcoming seasonal anime from Jikan")
            return

        new_entries = [e for e in entries if str(e.get("mal_id")) not in self.seen_upcoming]
        for entry in new_entries:
            embed = build_anime_embed(entry, note="📢 Newly listed upcoming anime")
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                logger.exception("Failed to post upcoming-anime notification")
                continue
            self.seen_upcoming.add(str(entry.get("mal_id")))

        if new_entries:
            storage.save_json(SEEN_UPCOMING_FILE, list(self.seen_upcoming))

    @upcoming_loop.before_loop
    async def before_upcoming_loop(self):
        await self.bot.wait_until_ready()

    # --- Loop 2: release / new-episode notifications for the watchlist ----

    @tasks.loop(hours=24)
    async def release_loop(self):
        if not self.watchlist:
            return

        channel = resolve_channel(
            self.bot,
            config.RELEASE_CHANNEL_ID or config.NOTIFY_CHANNEL_ID,
            config.RELEASE_CHANNEL_NAME or config.NOTIFY_CHANNEL_NAME,
        )
        if not channel:
            logger.warning(
                "Release notify channel not found; check RELEASE_CHANNEL_ID / RELEASE_CHANNEL_NAME."
            )
            return

        today = datetime.now(timezone.utc)
        weekday = WEEKDAYS[today.weekday()]
        today_str = today.strftime("%Y-%m-%d")

        try:
            schedule_entries = await self.jikan.get_schedules(weekday, max_pages=3)
        except JikanAPIError:
            logger.exception("Failed to fetch schedules from Jikan")
            return

        schedule_by_id = {str(e.get("mal_id")): e for e in schedule_entries}
        changed = False
        for mal_id in self.watchlist:
            entry = schedule_by_id.get(mal_id)
            if not entry:
                continue
            if self.release_state.get(mal_id) == today_str:
                continue  # already notified today

            embed = build_anime_embed(entry, note="🆕 New episode airing today!")
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                logger.exception("Failed to post release notification")
                continue
            self.release_state[mal_id] = today_str
            changed = True

        if changed:
            storage.save_json(RELEASE_STATE_FILE, self.release_state)

    @release_loop.before_loop
    async def before_release_loop(self):
        await self.bot.wait_until_ready()

    # --- Watchlist management commands ------------------------------------

    @app_commands.command(name="watch", description="Add an anime (by MAL ID) to the release-notification watchlist")
    @app_commands.describe(mal_id="The MyAnimeList ID of the anime (the number in its MAL URL)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def watch(self, interaction: discord.Interaction, mal_id: int):
        await interaction.response.defer(ephemeral=True)
        key = str(mal_id)
        if key in self.watchlist:
            await interaction.followup.send(f"MAL ID `{mal_id}` is already on the watchlist.", ephemeral=True)
            return

        try:
            anime = await self.jikan.get_anime_full(mal_id)
        except JikanNotFoundError:
            await interaction.followup.send(f"No anime found with MAL ID `{mal_id}`.", ephemeral=True)
            return
        except JikanAPIError:
            await interaction.followup.send(
                "Couldn't verify that MAL ID with Jikan right now. Please try again later.", ephemeral=True
            )
            return

        self.watchlist.add(key)
        storage.save_json(WATCHLIST_FILE, list(self.watchlist))
        await interaction.followup.send(
            f"Added **{get_display_title(anime)}** (`{mal_id}`) to the release watchlist.", ephemeral=True
        )

    @app_commands.command(
        name="unwatch", description="Remove an anime (by MAL ID) from the release-notification watchlist"
    )
    @app_commands.describe(mal_id="The MyAnimeList ID to remove from the watchlist")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def unwatch(self, interaction: discord.Interaction, mal_id: int):
        key = str(mal_id)
        if key not in self.watchlist:
            await interaction.response.send_message(f"MAL ID `{mal_id}` is not on the watchlist.", ephemeral=True)
            return
        self.watchlist.discard(key)
        storage.save_json(WATCHLIST_FILE, list(self.watchlist))
        await interaction.response.send_message(f"Removed `{mal_id}` from the release watchlist.", ephemeral=True)

    @app_commands.command(name="watchlist", description="Show anime currently on the release-notification watchlist")
    async def watchlist_cmd(self, interaction: discord.Interaction):
        if not self.watchlist:
            await interaction.response.send_message(
                "The watchlist is empty. Add anime with `/watch <mal_id>`.", ephemeral=True
            )
            return
        ids = ", ".join(f"`{i}`" for i in sorted(self.watchlist, key=int))
        await interaction.response.send_message(f"Watched MAL IDs: {ids}", ephemeral=True)


async def setup(bot: commands.Bot):
    # Not used directly (cogs are constructed with a shared JikanClient in
    # bot.py's setup_hook), but kept for compatibility with `bot.load_extension`.
    await bot.add_cog(NotificationsCog(bot, bot.jikan))
