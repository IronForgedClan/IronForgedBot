import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.storage.types import StorageError


async def sub_raffle_end(self, interaction: discord.Interaction):
    """Ends raffle, disabling purchase of tickets.

    Expects provided interaction to have already deferred the response.
    """
    try:
        self._storage_client.end_raffle(
            normalize_discord_string(interaction.user.display_name).lower()
        )
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error ending raffle: {error}"
        )
        return

    await interaction.followup.send(
        "Raffle ended! Members can no longer purchase tickets."
    )
