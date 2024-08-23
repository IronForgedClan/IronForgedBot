import discord

from ironforgedbot.common.helpers import normalize_discord_string


def can_start_task(guild: discord.Guild, updates_channel_name: str):
    if updates_channel_name is None or "" == updates_channel_name:
        return None

    updates_channel = _find_channel(guild, updates_channel_name)
    if updates_channel is None:
        return None

    return updates_channel


def _find_channel(guild: discord.Guild, channel_name: str):
    for channel in guild.channels:
        if normalize_discord_string(channel.name).lower() == channel_name.lower():
            return channel


async def _send_discord_message_plain(channel, message):
    await channel.send(content=message)
