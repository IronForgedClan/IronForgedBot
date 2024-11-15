import io
from datetime import datetime

import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold, text_h2
from ironforgedbot.decorators import require_role


@require_role(ROLE.LEADERSHIP, ephemeral=True)
async def cmd_get_role_members(
    interaction: discord.Interaction,
    role: str,
):
    assert interaction.guild
    role = normalize_discord_string(role)
    count = 0
    output = ""

    for member in interaction.guild.members:
        user_roles = [role.name for role in member.roles]

        if role in user_roles:
            count += 1
            output += f"{normalize_discord_string(member.display_name)}, "

    if len(output) < 1:
        return await interaction.followup.send(
            f"No members with role '{text_bold(role)}' found."
        )

    discord_file = discord.File(
        fp=io.BytesIO(output[:-2].encode("utf-8")),
        filename=(
            f"{role.lower().replace(' ', '_')}_role_list_"
            f"{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt"
        ),
    )

    return await interaction.followup.send(
        (
            f"{text_h2('Member Role List')}"
            f"Found {text_bold(str(count))} members with the role '{text_bold(role)}'."
        ),
        file=discord_file,
    )
