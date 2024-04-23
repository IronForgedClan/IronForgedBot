import discord
from datetime import datetime

def build_error_message_embed(message:str) -> discord.Embed:
    embed = discord.Embed(
        description=message,
        color=discord.Color.red()
    )
    return embed

def build_response_embed(title:str, description:str, color: discord.Color) -> discord.Embed:
    embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )

    embed.timestamp = datetime.now();
    embed.set_footer(
        text="Iron Forged Bot",
        icon_url="https://avatars.githubusercontent.com/u/166751212?s=200&v=4"
    )

    return embed