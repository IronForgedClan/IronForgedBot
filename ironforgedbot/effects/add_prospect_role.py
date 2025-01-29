import logging
from datetime import datetime, timezone

import discord

from ironforgedbot.common.helpers import (
    datetime_to_discord_relative,
    get_discord_role,
    normalize_discord_string,
)
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def add_prospect_role(
    report_channel: discord.TextChannel, member: discord.Member
):
    storage_member = None
    error = False
    try:
        storage_member = await STORAGE.read_member(
            normalize_discord_string(member.display_name)
        )
    except StorageError:
        error = True

    if error or not storage_member:
        await report_channel.send(
            f":information: {member.mention} has been given the "
            f"{text_bold(ROLE.PROSPECT)} role without having the {text_bold(ROLE.MEMBER)} "
            "role. Adding correct roles to member and trying again..."
        )

        member_role = get_discord_role(report_channel.guild, ROLE.MEMBER)
        prospect_role = get_discord_role(report_channel.guild, ROLE.PROSPECT)
        if not member_role or not prospect_role:
            raise ValueError("Unable to access member or prospect role values")

        await member.add_roles(member_role, reason="Prospect role effect")
        await member.remove_roles(prospect_role, reason="Prospect role effect")
        await member.add_roles(prospect_role, reason="Prospect role effect")
        return

    report_message = await report_channel.send(
        f":information: {member.mention} has been given the "
        f"{text_bold(ROLE.PROSPECT)} role, saving timestamp..."
    )

    now = datetime.now(timezone.utc)
    storage_member.joined_date = now.isoformat()

    await STORAGE.update_members([storage_member], "BOT", "Added Prospect role")

    await report_message.edit(
        content=(
            f":information: {member.mention} has been given the "
            f"{text_bold(ROLE.PROSPECT)} role.\nJoin date saved: "
            f"{datetime_to_discord_relative(now, 'F')}"
        )
    )
