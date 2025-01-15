import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.tasks.job_sync_members import job_sync_members


async def add_member_role(report_channel: discord.TextChannel, member: discord.Member):
    await report_channel.send(
        f":information: {member.mention} has been given the {text_bold(ROLE.MEMBER)} "
        "role. Initiating member sync..."
    )

    await job_sync_members(report_channel.guild, report_channel)
