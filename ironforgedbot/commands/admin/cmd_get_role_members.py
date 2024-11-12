from datetime import datetime
import io
import discord
from ironforgedbot.common.helpers import (
    normalize_discord_string,
    validate_member_has_role,
)
from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role


@require_role(ROLES.LEADERSHIP, ephemeral=True)
async def cmd_get_role_members(
    interaction: discord.Interaction,
    role: str,
):
    assert interaction.guild
    role = normalize_discord_string(role)
    count = 0
    output = ""

    for member in interaction.guild.members:
        if validate_member_has_role(member, role):
            count += 1
            output += f"{normalize_discord_string(member.display_name)}, "

    if len(output) < 1:
        return await interaction.followup.send(
            f"No members with role '**{role}**' found."
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
            "## Member Role List\n"
            f"Found **{count}** members with the role '**{role}**'."
        ),
        file=discord_file,
    )
