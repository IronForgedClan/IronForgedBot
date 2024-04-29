from apscheduler.executors.base import logging
import discord

from ironforgedbot.common.helpers import normalize_discord_string

def validate_player_name_length(player: str) -> bool:
    if len(player) > 12 or len(player) is 0:
        return False
    return True

# validates if player is member of guild and returns member object
def validate_player(guild: discord.Guild, player:str):
    if not validate_player_name_length(player):
        logging.info(f"Player name '{player}' does not meet rsn length restrictions")
        return False

    for member in guild.members:
        if normalize_discord_string(member.display_name.lower()) == player.lower():
            return member

    logging.info(f"Player name '{player}' is not a member of this guild")
    return False

