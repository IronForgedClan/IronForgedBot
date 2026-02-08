from enum import StrEnum
from typing import List, Optional

import discord

BOOSTER_ROLE_NAME = "Server Booster"
PROSPECT_ROLE_NAME = "Prospect"
BLACKLISTED_ROLE_NAME = "Blacklisted"
BANNED_ROLE_NAME = "Slag"


class ROLE(StrEnum):
    GUEST = "Guest"
    APPLICANT = "Applicant"
    MEMBER = "Member"
    MODERATOR = "Moderator"
    STAFF = "Staff"
    BRIGADIER = "Brigadier"
    ADMIRAL = "Admiral"
    LEADERSHIP = "Leadership"  # Deprecated
    MARSHAL = "Marshal"
    OWNER = "Owners"

    def or_higher(self):
        """Returns all roles at this level or higher"""
        roles = list(ROLE)
        index = roles.index(self)
        return [role.value for role in roles[index:]]  # slice from current to end

    def or_lower(self):
        """Returns all roles at this level or below"""
        roles = list(ROLE)
        index = roles.index(self)
        return [
            role.value for role in roles[: index + 1]
        ]  # slice from start to current

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))

    @staticmethod
    def any():
        """Returns all roles in a list"""
        return list(ROLE)


def get_highest_privilage_role_from_member(member: discord.Member) -> Optional[ROLE]:
    member_role_names = {r.name.lower().strip() for r in member.roles}
    matching_roles = [
        role for role in ROLE if role.value.lower().strip() in member_role_names
    ]
    return max(matching_roles, default=None, key=lambda r: list(ROLE).index(r))


def check_member_has_role(
    member: discord.Member,
    required_role: ROLE,
    or_higher: Optional[bool] = False,
    or_lower: Optional[bool] = False,
) -> bool:
    member_roles = set(role.name for role in member.roles)
    acceptable_roles = set([required_role.value])

    if or_higher:
        acceptable_roles = set(ROLE(required_role).or_higher())

    if or_lower:
        acceptable_roles = set(ROLE(required_role).or_lower())

    member_roles = {role.lower().strip() for role in member_roles}
    acceptable_roles = {role.lower().strip() for role in acceptable_roles}

    if acceptable_roles & member_roles:
        return True

    return False


def member_has_any_roles(
    member: discord.Member,
    roles: List[ROLE],
) -> bool:
    """Check if a Discord member has the requested role."""
    required_roles = set([r.lower() for r in roles])
    actual_roles = set([r.name.lower() for r in member.roles])

    return len(required_roles & actual_roles) > 0


def is_member_banned_by_role(member: discord.Member | None) -> bool:
    """Check if a Discord member has the banned (Slag) role.

    Note: Prefer checking the is_banned flag on the database Member model.
    This function is for checking Discord roles directly when needed.
    """
    if not member:
        raise Exception()

    member_roles = {role.name.lower().strip() for role in member.roles}
    return BANNED_ROLE_NAME.lower() in member_roles


def has_prospect_role(member: discord.Member) -> bool:
    """Check if a Discord member has the Prospect role."""
    member_roles = {role.name.lower().strip() for role in member.roles}
    return PROSPECT_ROLE_NAME.lower() in member_roles


def has_booster_role(member: discord.Member) -> bool:
    """Check if a Discord member has the Server Booster role."""
    member_roles = {role.name.lower().strip() for role in member.roles}
    return BOOSTER_ROLE_NAME.lower() in member_roles


def has_blacklisted_role(member: discord.Member) -> bool:
    """Check if a Discord member has the Blacklisted role."""
    member_roles = {role.name.lower().strip() for role in member.roles}
    return BLACKLISTED_ROLE_NAME.lower() in member_roles


def get_member_flags_from_discord(discord_member: discord.Member) -> dict[str, bool]:
    """Extract all flag values from a Discord member's roles."""
    return {
        "is_booster": has_booster_role(discord_member),
        "is_prospect": has_prospect_role(discord_member),
        "is_blacklisted": has_blacklisted_role(discord_member),
        "is_banned": is_member_banned_by_role(discord_member),
    }


def get_flag_changes(db_member, discord_flags: dict[str, bool]) -> list[str]:
    """Compare DB member flags to Discord flags, return list of change descriptions."""
    changes = []
    if db_member.is_booster != discord_flags["is_booster"]:
        changes.append(f"Booster: {discord_flags['is_booster']}")
    if db_member.is_prospect != discord_flags["is_prospect"]:
        changes.append(f"Prospect: {discord_flags['is_prospect']}")
    if db_member.is_blacklisted != discord_flags["is_blacklisted"]:
        changes.append(f"Blacklisted: {discord_flags['is_blacklisted']}")
    if db_member.is_banned != discord_flags["is_banned"]:
        changes.append(f"Banned: {discord_flags['is_banned']}")
    return changes
