import logging

import discord
from discord.ui import Button, View

from ironforgedbot.commands.admin.cmd_get_role_members import cmd_get_role_members
from ironforgedbot.commands.hiscore.cmd_breakdown import cmd_breakdown
from ironforgedbot.commands.hiscore.cmd_score import cmd_score
from ironforgedbot.commands.holiday.cmd_trick_or_treat import cmd_trick_or_treat
from ironforgedbot.commands.ingots.cmd_add_remove_ingots import cmd_add_remove_ingots
from ironforgedbot.commands.ingots.cmd_view_ingots import cmd_view_ingots
from ironforgedbot.commands.lookup.cmd_whois import cmd_whois
from ironforgedbot.commands.raffle.cmd_raffle import cmd_raffle
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.roles import ROLE

logger = logging.getLogger(__name__)


@log_command_execution(logger)
async def cmd_debug_commands(original_interaction: discord.Interaction):
    commands = {
        "score": {"callback": lambda interaction: cmd_score(interaction)},
        "breakdown": {"callback": lambda interaction: cmd_breakdown(interaction)},
        "ingots": {"callback": lambda interaction: cmd_view_ingots(interaction)},
        "add ingots": {
            "callback": lambda interaction: cmd_add_remove_ingots(
                interaction,
                f"{interaction.user.display_name},test,a,b,c,d,e,f,g",
                500_000,
                "test add",
            )
        },
        "remove ingots": {
            "callback": lambda interaction: cmd_add_remove_ingots(
                interaction,
                f"{interaction.user.display_name},test,a,b,c,d,e,f,g",
                -500_000,
                "test remove",
            )
        },
        "raffle": {"callback": lambda interaction: cmd_raffle(interaction)},
        "get role members": {
            "callback": lambda interaction: cmd_get_role_members(
                interaction, ROLE.MEMBER
            )
        },
        "trick or treat": {
            "callback": lambda interaction: cmd_trick_or_treat(interaction)
        },
        "who is": {
            "callback": lambda interaction: cmd_whois(
                interaction, interaction.user.display_name
            )
        },
    }

    view = View()

    for command_name, command_data in commands.items():
        button = Button(label=command_name, style=discord.ButtonStyle.primary)

        async def button_callback(interaction, callback=command_data["callback"]):
            await callback(interaction)

        button.callback = button_callback
        view.add_item(button)

    await original_interaction.response.send_message(
        "## Select Command", view=view, ephemeral=True
    )
