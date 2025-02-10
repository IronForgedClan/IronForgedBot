import logging
from datetime import datetime, timezone

import discord

from ironforgedbot.common.helpers import (
    datetime_to_discord_relative,
    get_discord_role,
    normalize_discord_string,
)
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


async def add_prospect_role(
    report_channel: discord.TextChannel, member: discord.Member
):
    logger.info(f"{member.display_name} has been given the Prospect role...")

    if check_member_has_role(member, ROLE.APPLICANT):
        logger.info(f"{member.display_name} has Applicant role, removing...")
        applicant_role = get_discord_role(report_channel.guild, ROLE.APPLICANT)
        if applicant_role is None:
            raise ValueError("Unable to access Applicant role values")

        await member.remove_roles(
            applicant_role, reason="Prospect: remove Applicant role"
        )

    if check_member_has_role(member, ROLE.GUEST):
        logger.info(f"{member.display_name} has Guest role, removing...")
        guest_role = get_discord_role(report_channel.guild, ROLE.GUEST)
        if guest_role is None:
            raise ValueError("Unable to access Guest role values")

        await member.remove_roles(guest_role, reason="Prospect: remove Guest role")

    storage_member = None
    error = False
    try:
        storage_member = await STORAGE.read_member(
            normalize_discord_string(member.display_name)
        )
    except StorageError:
        error = True

    if error or not storage_member:
        logger.info(
            f"{member.display_name} not found in storage, adding Member role and trying again..."
        )
        await report_channel.send(
            f":information: {member.mention} has been given the "
            f"{text_bold(ROLE.PROSPECT)} role without having the {text_bold(ROLE.MEMBER)} "
            "role. Adding correct roles to member and trying again..."
        )

        member_role = get_discord_role(report_channel.guild, ROLE.MEMBER)
        prospect_role = get_discord_role(report_channel.guild, ROLE.PROSPECT)
        if member_role is None or prospect_role is None:
            raise ValueError("Unable to access Member or Prospect role values")

        await member.remove_roles(
            prospect_role, reason="Prospect: not in storage, toggling role"
        )
        await member.add_roles(member_role, reason="Prospect: adding Member role")
        await member.add_roles(prospect_role, reason="Prospect: adding Prospect role")
        return

    report_message = await report_channel.send(
        f":information: {member.mention} has been given the "
        f"{text_bold(ROLE.PROSPECT)} role, saving timestamp..."
    )

    now = datetime.now(timezone.utc)
    storage_member.joined_date = now.isoformat()

    await STORAGE.update_members(
        [storage_member], "BOT", "Saving Prospect joined timestamp"
    )

    await report_message.edit(
        content=(
            f":information: {member.mention} has been given the "
            f"{text_bold(ROLE.PROSPECT)} role.\nJoin date saved: "
            f"{datetime_to_discord_relative(now, 'F')}"
        )
    )
    logger.info(f"Finished adding Prospect role to {member.display_name}.")
