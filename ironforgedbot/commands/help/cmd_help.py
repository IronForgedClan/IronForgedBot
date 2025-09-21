import re
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands

from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators import require_role


@require_role(ROLE.MEMBER)
@app_commands.describe(role="(Leadership only) View commands as this role")
async def cmd_help(interaction: discord.Interaction, role: Optional[str] = None):
    assert interaction.guild

    # Map Discord role names -> internal roles
    ROLE_NAME_MAP = {
        "Leadership": ROLE.LEADERSHIP,
        "Member": ROLE.MEMBER,
    }

    user_roles = {role.name for role in interaction.user.roles}
    user_internal_roles = {
        internal_role
        for name, internal_role in ROLE_NAME_MAP.items()
        if name in user_roles
    }

    # Only allow Leadership to simulate another role
    effective_roles = user_internal_roles
    if ROLE.LEADERSHIP in user_internal_roles and role:
        role = role.lower().strip()
        if role == "member":
            effective_roles = {ROLE.MEMBER}

    # Load and parse command_tree.py
    command_roles = {}
    with open("ironforgedbot/command_tree.py", "r") as file:
        lines = file.readlines()

    current_command_name = None
    for line in lines:
        name_match = re.search(r'name\s*=\s*"(.*?)"', line)
        meta_match = re.search(
            r"#\s*ROLE:(\w+)(?:\s*\|\s*TYPE:(\w+))?(?:\s*\|\s*RANGE:([\d/]+)-([\d/]+))?",
            line,
        )

        if name_match:
            current_command_name = name_match.group(1)

        if meta_match and current_command_name:
            role_str = meta_match.group(1) or "MEMBER"
            role_required = getattr(ROLE, role_str.upper(), ROLE.MEMBER)

            command_type = (meta_match.group(2) or "PERMANENT").upper()
            start_date = meta_match.group(3)
            end_date = meta_match.group(4)

            command_roles[current_command_name] = {
                "required_role": role_required,
                "type": command_type,
                "start_date": start_date,
                "end_date": end_date,
            }

    # Evaluate visible commands
    visible_commands = []
    today = datetime.today()

    for name, meta in command_roles.items():
        role_required = meta["required_role"]
        command_type = meta["type"]

        if (
            role_required == ROLE.MEMBER
            and ROLE.MEMBER not in effective_roles
            and ROLE.LEADERSHIP not in effective_roles
        ):
            continue
        if role_required == ROLE.LEADERSHIP and ROLE.LEADERSHIP not in effective_roles:
            continue

        if command_type == "HOLIDAY":
            try:
                start = datetime.strptime(meta["start_date"], "%m/%d").replace(
                    year=today.year
                )
                end = datetime.strptime(meta["end_date"], "%m/%d").replace(
                    year=today.year
                )
                if not (start <= today <= end):
                    continue
            except Exception:
                continue

        visible_commands.append(f"/{name}")

    # Sort and group commands into rows
    visible_commands.sort()
    rows = []
    for i in range(0, len(visible_commands), 2):
        left = visible_commands[i]
        right = visible_commands[i + 1] if i + 1 < len(visible_commands) else ""
        row = f"{left:<25}{right}"
        rows.append(row)

    full_description = "```\n" + "\n".join(rows) + "\n```"

    embed = discord.Embed(
        title="Available Commands",
        description=full_description or "You have no available commands.",
        color=discord.Color.blurple(),
    )

    await interaction.followup.send(embed=embed, ephemeral=True)
