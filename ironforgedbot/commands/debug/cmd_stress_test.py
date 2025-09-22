import asyncio
import logging

import discord
from discord.ui import Button, View

from ironforgedbot.common.helpers import get_text_channel
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.config import CONFIG
from ironforgedbot.tasks.job_check_activity import job_check_activity
from ironforgedbot.tasks.job_sync_members import job_sync_members
from ironforgedbot.tasks.job_membership_discrepancies import (
    job_check_membership_discrepancies,
)
from ironforgedbot.tasks.job_refresh_ranks import job_refresh_ranks
from ironforgedbot.common.logging_utils import log_command_execution

logger = logging.getLogger(__name__)


@log_command_execution(logger)
async def cmd_stress_test(interaction: discord.Interaction):
    commands = {
        "message spam": {
            "callback": lambda interaction: message_request_spam(interaction)
        },
        "run all automations": {
            "callback": lambda interaction: run_all_automations(interaction)
        },
    }

    view = View()
    for command_name, command_data in commands.items():
        button = Button(label=command_name, style=discord.ButtonStyle.danger)

        async def button_callback(interaction, callback=command_data["callback"]):
            await callback(interaction)

        button.callback = button_callback
        view.add_item(button)

    await interaction.response.send_message(
        "## Stress Options", view=view, ephemeral=True
    )


async def message_request_spam(
    interaction: discord.Interaction, users: int = 5, request_per_user: int = 10
):
    await interaction.response.send_message("Starting...")

    async def send_message(channel, user_id):
        for i in range(request_per_user):
            await channel.send(f"Simulated message from user {user_id} #{i}")
            await asyncio.sleep(0.2)

    tasks = []
    channel = interaction.channel

    for user_id in range(users):
        tasks.append(send_message(channel, user_id))

    await asyncio.gather(*tasks)
    await channel.send(
        f"## Complete\nSimulated {text_bold(str(request_per_user))} requests for {text_bold(str(users))} users."
    )


async def run_all_automations(interaction: discord.Interaction):
    assert interaction.guild
    assert interaction.channel_id
    channel = get_text_channel(interaction.guild, interaction.channel_id)
    assert channel

    tasks = []
    tasks.append(job_sync_members(interaction.guild, channel))
    tasks.append(job_refresh_ranks(interaction.guild, channel))
    tasks.append(job_check_activity(channel))
    tasks.append(
        job_check_membership_discrepancies(
            interaction.guild, channel, CONFIG.WOM_API_KEY, CONFIG.WOM_GROUP_ID
        )
    )

    asyncio.gather(*tasks)

    await interaction.response.send_message(f"Starting {len(tasks)} jobs...")
