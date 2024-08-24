import random

import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError


async def sub_raffle_select_winner(interaction: discord.Interaction):
    """Chooses a winner & winning amount. Clears storage of all tickets."""
    try:
        current_tickets = STORAGE.read_raffle_tickets()
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error ending raffle: {error}"
        )
        return

    try:
        members = STORAGE.read_members()
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error reading current members: {error}"
        )
        return

    # Now we have ID:tickets & RSN:ID
    # Morph these into a List[RSN], where RSN appears once for each ticket
    # First, make our list of members a dictionary for faster lookups
    id_to_runescape_name = {}
    for member in members:
        id_to_runescape_name[member.id] = member.runescape_name

    entries = []
    for id, ticket_count in current_tickets.items():
        # Account for users who left clan since buying tickets.
        if id_to_runescape_name.get(id) is not None:
            entries.extend([id_to_runescape_name.get(id)] * ticket_count)

    winner = entries[random.randrange(0, len(entries))]

    winnings = len(entries) * 2500

    # TODO: Make this more fun by adding an entries file or rendering a graphic
    await interaction.followup.send(
        f"{winner} has won {winnings} ingots out of {len(entries)} entries!"
    )

    try:
        STORAGE.delete_raffle_tickets(
            normalize_discord_string(interaction.user.display_name).lower()
        )
    except StorageError as error:
        await send_error_response(
            interaction, f"Encountered error clearing ticket storage: {error}"
        )
        return
