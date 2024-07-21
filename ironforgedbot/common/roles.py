from enum import StrEnum
from typing import Optional

import discord

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.ranks import RANKS


class ROLES(StrEnum):
    LEADERSHIP = "Leadership"
    MEMBER = "Member"
    PROSPECT = "Prospect"


def extract_roles(member: discord.Member) -> list[str]:
    roles = []
    for role in member.roles:
        normalized_role = normalize_discord_string(role.name)
        if "" == normalized_role:
            continue
        roles.append(normalized_role)

    return roles


def find_rank(roles: list[str]) -> Optional[RANKS]:
    for role in roles:
        if RANKS.has_value(role):
            return RANKS(role)
    return None


def is_member(roles: list[str]) -> bool:
    for role in roles:
        if ROLES.MEMBER.lower() == role.lower():
            return True

    return False


def is_prospect(roles: list[str]) -> bool:
    for role in roles:
        if ROLES.PROSPECT.lower() == role.lower():
            return True

    return False
