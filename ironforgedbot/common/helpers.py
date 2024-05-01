from discord import Emoji, Interaction, Guild
from collections.abc import Sequence

emojiCache = dict[str, Emoji]()

def normalize_discord_string(nick: str) -> str:
    """Strips Discord nickname down to plaintext."""
    if nick is None:
        return ""

    if nick.isascii():
        return nick

    new_nick = []
    for letter in nick:
        if letter.isascii():
            new_nick.append(letter)
    return "".join(new_nick).strip()

def validate_user_request(interaction: Interaction, playername: str):
    if not interaction.guild:
        raise ReferenceError("Error accessing server")

    if interaction.is_expired():
        raise ReferenceError("Interaction has expired")

    playername = normalize_discord_string(playername)
    if len(playername) > 12 or len(playername) < 1:
        raise ValueError("Player name can only be 1-12 characters long")

    member = find_member_by_nickname(interaction.guild, playername)

    return member, playername

def find_member_by_nickname(guild: Guild, target_name:str):
    for member in guild.members:
        normalized_display_name = normalize_discord_string(member.display_name.lower())
        if normalized_display_name == normalize_discord_string(target_name.lower()):
            if not member.nick or len(member.nick) < 1:
                raise ValueError(f"Member '**{member.display_name}**' does not have a nickname set")
            return member

    raise ValueError(f"Player '**{target_name}**' is not a member of this server")

def calculate_percentage(part, whole) -> int:
    return round(100 * float(part) / float(whole))


def find_emoji(list: Sequence[Emoji], target: str):
    if target in emojiCache:
        return emojiCache[target]

    for emoji in list:
        if emoji.available and emoji.name == target:
            emojiCache[emoji.name] = emoji
            return emoji

    return ":grin:"
