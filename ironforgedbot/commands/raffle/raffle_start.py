import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.storage.types import StorageError


async def sub_raffle_start(self, interaction: discord.Interaction):
    """Starts a raffle, enabling purchase of raffle tickets.

    Expects provided interaction to have already deferred the response.
    """
    try:
        self._storage_client.start_raffle(
            normalize_discord_string(interaction.user.display_name).lower()
        )
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error starting raffle: {error}"
        )
        return

    await interaction.followup.send(
        "Started raffle! Members can now use ingots to purchase tickets."
    )
