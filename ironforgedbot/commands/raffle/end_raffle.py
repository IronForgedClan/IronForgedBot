import logging
import random
from typing import Optional
import discord

from ironforgedbot.commands.raffle.build_winner_image import build_winner_image_file
from ironforgedbot.common.helpers import (
    find_emoji,
    find_member_by_nickname,
    normalize_discord_string,
)
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.text_formatters import text_bold, text_sub
from ironforgedbot.state import STATE
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def handle_end_raffle_error(
    parent_message: Optional[discord.Message], interaction: discord.Interaction, message
):
    if parent_message:
        parent_message = await parent_message.delete()

    return await send_error_response(interaction, message)


async def handle_end_raffle(
    parent_message: Optional[discord.Message], interaction: discord.Interaction
):
    await interaction.response.defer()
    assert interaction.guild

    if parent_message:
        parent_message = await parent_message.edit(
            content="## Ending raffle\nSelecting winner, standby...",
            embed=None,
            view=None,
        )

    try:
        current_tickets = await STORAGE.read_raffle_tickets()
    except StorageError as error:
        return await handle_end_raffle_error(
            parent_message, interaction, f"Encountered error ending raffle: {error}"
        )

    ticket_icon = find_emoji(None, "Raffle_Ticket")
    if len(current_tickets) < 1:
        logger.info("Raffle ended with no tickets sold.")
        STATE.state["raffle_on"] = False
        STATE.state["raffle_price"] = 0

        if parent_message:
            parent_message = await parent_message.delete()

        return await interaction.followup.send(
            content=f"## {ticket_icon} Raffle Ended\n\nNo tickets were sold. There is no winner 🤷‍♂️."
        )

    try:
        members = await STORAGE.read_members()
    except StorageError as error:
        return await handle_end_raffle_error(
            parent_message,
            interaction,
            f"Encountered error reading current members: {error}",
        )

    # Calculate valid entries
    current_members = {}
    for member in members:
        current_members[member.id] = member.runescape_name

    total_tickets = 0
    valid_entries = []
    for id, ticket_count in current_tickets.items():
        total_tickets += ticket_count
        # Ignore members who have left the clan since buying tickets
        if current_members.get(id) is not None:
            valid_entries.extend([current_members.get(id)] * ticket_count)

    if len(valid_entries) < 1:
        logger.info("Raffle ended with no valid tickets to select from.")
        return await handle_end_raffle_error(
            parent_message,
            interaction,
            "Raffle ended without any valid entries. May require manual data purge.",
        )

    # Calculate winner
    random.shuffle(valid_entries)
    winner = random.choice(valid_entries)
    winning_discord_member = find_member_by_nickname(interaction.guild, winner)

    winnings = int(total_tickets * (STATE.state["raffle_price"] / 2))

    logger.info(f"Raffle entries: {valid_entries}")
    logger.info(f"Raffle winner: {winner} ({winning_discord_member.id})")

    # Award winnings
    try:
        member = await STORAGE.read_member(
            normalize_discord_string(winning_discord_member.display_name)
        )
    except StorageError as error:
        return await handle_end_raffle_error(parent_message, interaction, error.message)

    if member is None:
        return await handle_end_raffle_error(
            parent_message,
            interaction,
            f"Winning member '{winning_discord_member.display_name}' not found in storage.",
        )

    member.ingots += winnings

    try:
        await STORAGE.update_members(
            [member],
            interaction.user.display_name,
            note=f"[BOT] Raffle winnings ({winnings:,})",
        )
    except StorageError as error:
        return await handle_end_raffle_error(parent_message, interaction, error.message)

    # Announce winner
    ingot_icon = find_emoji(None, "Ingot")
    file = await build_winner_image_file(winner, int(winnings))

    winner_ticket_count = current_tickets[winning_discord_member.id]
    winner_spent = winner_ticket_count * STATE.state["raffle_price"]
    winner_profit = winnings - winner_spent
    await interaction.followup.send(
        (
            f"## {ticket_icon} Congratulations {winning_discord_member.mention}!!\n"
            f"You have won {ingot_icon} {text_bold(f"{winnings:,}")} ingots!\n\n"
            f"You spent {ingot_icon} {text_bold(f"{winner_spent:,}")} on {ticket_icon} "
            f"{text_bold(f"{winner_ticket_count:,}")} tickets.\n"
            f"Resulting in {ingot_icon} {text_bold(f"{winner_profit:,}")} profit.\n"
            + (f"{text_sub('ouch')}\n\n" if winner_profit < 0 else "\n")
            + f"There were a total of {ticket_icon} {text_bold(f"{total_tickets:,}")} entries.\n"
            "Thank you everyone for participating!"
        ),
        file=file,
    )

    # Cleanup
    STATE.state["raffle_on"] = False
    STATE.state["raffle_price"] = 0
    logger.info("Raffle ended.")

    try:
        await STORAGE.delete_raffle_tickets(
            normalize_discord_string(interaction.user.display_name).lower()
        )
    except StorageError as error:
        return await handle_end_raffle_error(
            parent_message,
            interaction,
            f"Encountered error clearing ticket storage: {error}",
        )

    if parent_message:
        parent_message = await parent_message.delete()
