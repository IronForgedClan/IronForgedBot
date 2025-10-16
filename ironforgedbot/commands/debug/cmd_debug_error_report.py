import logging
from typing import Literal, Optional
from unittest.mock import Mock

import discord
from discord import app_commands

from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.decorators import require_role

logger = logging.getLogger(__name__)


@require_role(ROLE.LEADERSHIP)
@log_command_execution(logger)
@app_commands.describe(
    role_simulation="Role to simulate in the error report (member, leadership, guest)"
)
@app_commands.choices(
    role_simulation=[
        app_commands.Choice(name="Member", value="member"),
        app_commands.Choice(name="Leadership", value="leadership"),
        app_commands.Choice(name="Guest", value="guest"),
    ]
)
async def cmd_debug_error_report(
    interaction: discord.Interaction,
    role_simulation: Optional[Literal["member", "leadership", "guest"]] = "member",
):
    """Debug command to test error reporting functionality with phantom parameters.

    Arguments:
        interaction: Discord Interaction from CommandTree.
        role_simulation: Role to simulate (member, leadership, guest). Defaults to member.
    """
    mock_command = Mock()
    mock_command.name = "phantom_test_command"

    original_command = interaction.command
    original_data = getattr(interaction, "data", None)

    interaction.data = {
        "options": [
            {"name": "player_name", "value": "TestPlayer123"},
            {"name": "amount", "value": 50000},
            {
                "name": "reason",
                "value": "Debug test with special characters & symbols 🧪",
            },
            {"name": "debug_flag", "value": True},
            {"name": "category", "value": "testing"},
            {"name": "nested_param", "value": "complex_value_with_underscores"},
            {"name": "emoji_param", "value": "🎯🔥💎"},
        ]
    }

    interaction.command = mock_command

    guild_member = interaction.guild.get_member(interaction.user.id)
    original_roles = guild_member.roles if guild_member else []

    try:
        role_sim = role_simulation.lower() if role_simulation else "member"
        await interaction.response.send_message(
            f"🧪 **Debug Error Report Test**\n\n"
            f"Simulating phantom command `{mock_command.name}` with role: **{role_sim}**\n"
            f"Check the admin channel for the error report with parameters and log attachment.",
            ephemeral=True,
        )

        test_error_message = (
            f"Debug test error report from phantom command. "
            f"This is testing the error reporting system with multiple parameters "
            f"and role simulation ({role_sim}). "
            f"Triggered by: {interaction.user.mention}"
        )

        await send_error_response(interaction, test_error_message)

    finally:
        interaction.command = original_command
        if original_data is not None:
            interaction.data = original_data
        else:
            if hasattr(interaction, "data"):
                delattr(interaction, "data")
