import logging
import random
from typing import Optional

import discord
from sqlalchemy import text

from ironforgedbot.commands.raffle.build_winner_image import build_winner_image_file
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.text_formatters import text_bold, text_sub
from ironforgedbot.database.database import db
from ironforgedbot.services.service_factory import (
    create_ingot_service,
    create_member_service,
    create_raffle_service,
)
from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)


@log_command_execution(logger, interaction_position=1)
async def handle_end_raffle_error(
    parent_message: Optional[discord.Message], interaction: discord.Interaction, message
):
    if parent_message:
        parent_message = await parent_message.delete()

    return await send_error_response(interaction, message)


@log_command_execution(logger, interaction_position=1)
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

    ticket_icon = find_emoji("Raffle_Ticket")

    async with db.get_session() as session:
        raffle_service = create_raffle_service(session)
        total_tickets = await raffle_service.get_raffle_ticket_total()
        valid_tickets = await raffle_service.get_all_valid_raffle_tickets()

        if total_tickets < 1:
            STATE.state["raffle_on"] = False
            STATE.state["raffle_price"] = 0

            if parent_message:
                parent_message = await parent_message.delete()

            return await interaction.followup.send(
                content=(
                    f"## {ticket_icon} Raffle Ended\n\nNo tickets were sold. "
                    "There is no winner 🤷‍♂️."
                )
            )

        if len(valid_tickets) < 1:
            return await handle_end_raffle_error(
                parent_message,
                interaction,
                "Raffle ended without any valid entries.",
            )

        # Select winner
        entries: dict[str, int] = {}
        for ticket in valid_tickets:
            entries[ticket.member_id] = ticket.quantity

        winner_id = random.choices(
            list(entries.keys()), weights=list(entries.values()), k=1
        )[0]
        winner_qty = entries[winner_id]

        member_service = create_member_service(session)
        winning_member = await member_service.get_member_by_id(winner_id)

        if not winning_member:
            return await handle_end_raffle_error(
                parent_message,
                interaction,
                f"Error finding winner's details.\n{winner_id}",
            )

        # Award winnings
        ingot_service = create_ingot_service(session)
        winnings = int(total_tickets * int(STATE.state["raffle_price"] / 2))

        result = await ingot_service.try_add_ingots(
            winning_member.discord_id, winnings, None, f"Raffle winnings: ({winnings})"
        )
        if not result.status:
            return await handle_end_raffle_error(
                parent_message, interaction, result.message
            )

        # Announce winner
        winner_spent = winner_qty * STATE.state["raffle_price"]
        winner_profit = winnings - winner_spent

        winning_discord_member = interaction.guild.get_member(winning_member.discord_id)
        assert winning_discord_member

        ingot_icon = find_emoji("Ingot")
        file = await build_winner_image_file(winning_member.nickname, int(winnings))

        tickets_sold_string = (
            (
                f"one of your {ticket_icon} {text_bold(f'{winner_qty:,}')} tickets "
                "was chosen!\n"
            )
            if winner_qty > 1
            else f"your {text_bold('one and only')} ticket was chosen! Nice RNG.\n"
        )
        winnings_string = (
            (
                f"Leaving you with {ingot_icon} {text_bold(f'{winner_profit:,}')} pure "
                "profit. Nice.\n"
            )
            if winner_profit > 0
            else (
                f"Which means you actually lost {ingot_icon} "
                f"{text_bold(f'{winner_profit:,}')} ingots. Reckless spending. "
                "Unlucky bud.\n"
            )
        )
        await interaction.followup.send(
            (
                f"## {ticket_icon} Congratulations {winning_discord_member.mention}!!\n"
                f"You have won the raffle jackpot of {ingot_icon} "
                f"{text_bold(f'{winnings:,}')} ingots!\n\n"
                f"Out of {ticket_icon} {text_bold(f'{total_tickets:,}')} tickets sold, "
                + tickets_sold_string
                + f"\nYou spent a total of {ingot_icon} "
                f"{text_bold(f'{winner_spent:,}')} ingots. "
                + winnings_string
                + "\nThank you everyone for participating!"
            ),
            file=file,
        )

        # Cleanup
        STATE.state["raffle_on"] = False
        STATE.state["raffle_price"] = 0
        await raffle_service.delete_all_tickets()

        if parent_message:
            parent_message = await parent_message.delete()
