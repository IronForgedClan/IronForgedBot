import logging
from typing import Tuple
from discord import Interaction, Guild, Member


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


def validate_user_request(
    interaction: Interaction, playername: str
) -> Tuple[Member, str]:
    if not interaction.guild:
        logging.error(f"Error accessing guild ({interaction.id})")
        raise ReferenceError("Error accessing server")

    if interaction.is_expired():
        logging.info(f"Interaction has expired ({interaction.id})")
        raise ReferenceError("Interaction has expired")

    playername = validate_playername(playername)
    member = find_member_by_nickname(interaction.guild, playername)

    return member, playername


def validate_playername(playername: str) -> str:
    playername = normalize_discord_string(playername)

    if len(playername) > 12 or len(playername) < 1:
        logging.info(f"RSN length incorrect: '{playername}'")
        raise ValueError("RSN can only be 1-12 characters long")

    return playername


def validate_protected_request(
    interaction: Interaction, playername: str, required_role: str
) -> Tuple[Member, str]:
    member, playername = validate_user_request(interaction, playername)
    roles = member.roles

    for role in roles:
        if role.name == required_role:
            return member, playername

    raise ValueError(
        f"Member '{member.display_name}' does not have permission for this action"
    )


def find_member_by_nickname(guild: Guild, target_name: str):
    if not guild.members or len(guild.members) < 1:
        raise ReferenceError("Error accessing server members")

    for member in guild.members:
        normalized_display_name = normalize_discord_string(member.display_name.lower())
        if normalized_display_name == normalize_discord_string(target_name.lower()):
            if not member.nick or len(member.nick) < 1:
                logging.info(f"{member.display_name} has no nickname set")
                raise ValueError(
                    f"Member '**{member.display_name}**' does not have a nickname set"
                )
            return member

    raise ValueError(f"Player '**{target_name}**' is not a member of this server")


def calculate_percentage(part, whole) -> int:
    return round(100 * float(part) / float(whole))
