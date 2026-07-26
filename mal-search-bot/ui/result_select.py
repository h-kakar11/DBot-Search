"""Disambiguation dropdown UI for switching between multiple search matches."""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import discord

from utils.embed_builder import get_english_title

logger = logging.getLogger("mal_search_bot.ui.result_select")

EmbedBuilder = Callable[..., discord.Embed]

MAX_EXTRA_RESULTS = 5
DISAMBIGUATION_TIMEOUT = 60.0


class ResultSelect(discord.ui.Select):
    """A select menu letting the user switch the displayed embed to another match."""

    def __init__(self, results: list[dict[str, Any]], embed_builder: EmbedBuilder) -> None:
        """Build the dropdown options from up to `MAX_EXTRA_RESULTS` result entries."""
        self._results = results[:MAX_EXTRA_RESULTS]
        self._embed_builder = embed_builder

        options = [
            discord.SelectOption(label=get_english_title(entry)[:100], value=str(i))
            for i, entry in enumerate(self._results)
        ]

        super().__init__(
            placeholder="Show a different match...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Rebuild and swap in the embed for the selected result."""
        try:
            index = int(self.values[0])
            data = self._results[index]
            embed = self._embed_builder(data)
            await interaction.response.edit_message(embed=embed, view=self.view)
        except Exception:
            logger.exception("Failed to handle disambiguation selection.")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Sorry, something went wrong updating that selection.", ephemeral=True
                )


class ResultView(discord.ui.View):
    """View holding the disambiguation select menu; disables itself after a timeout."""

    def __init__(
        self,
        results: list[dict[str, Any]],
        embed_builder: EmbedBuilder,
        timeout: float = DISAMBIGUATION_TIMEOUT,
    ) -> None:
        """Attach a `ResultSelect` built from `results` to this view."""
        super().__init__(timeout=timeout)
        self.message: Optional[discord.Message] = None
        self.add_item(ResultSelect(results, embed_builder))

    async def on_timeout(self) -> None:
        """Disable the select menu once the view times out, editing the message if possible."""
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                logger.debug("Could not edit message to disable expired dropdown.")


async def send_result_with_dropdown(
    interaction: discord.Interaction,
    primary: dict[str, Any],
    extras: list[dict[str, Any]],
    embed_builder: EmbedBuilder,
    note: Optional[str] = None,
) -> None:
    """Send the primary result embed, attaching a disambiguation dropdown if needed.

    Args:
        interaction: The (already-deferred) interaction to reply to.
        primary: The top/best-matching result entry to show as the main embed.
        extras: Additional result entries (up to `MAX_EXTRA_RESULTS`) offered
            via a dropdown menu for the user to switch between.
        embed_builder: Callable that turns a result entry into a `discord.Embed`.
        note: Optional footer note to add to the primary embed (e.g. a fallback notice).
    """
    embed = embed_builder(primary, note=note) if note else embed_builder(primary)

    view: Optional[ResultView] = None
    if extras:
        count = len(extras)
        plural = "es" if count != 1 else ""
        dropdown_note = f"{count} other match{plural} found — use the dropdown below."
        existing_footer = embed.footer.text if embed.footer else None
        combined = f"{existing_footer} | {dropdown_note}" if existing_footer else dropdown_note
        embed.set_footer(text=combined)
        view = ResultView(extras, embed_builder)

    try:
        if view is not None:
            message = await interaction.followup.send(embed=embed, view=view)
            view.message = message
        else:
            await interaction.followup.send(embed=embed)
    except discord.HTTPException:
        logger.exception("Failed to send search result via followup.")
