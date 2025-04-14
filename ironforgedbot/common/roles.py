from enum import StrEnum
from typing import List, Optional

import discord


class ROLE(StrEnum):
    SLAG = "Slag"
    GUEST = "Guest"
    APPLICANT = "Applicant"
    PROSPECT = "Prospect"
    MEMBER = "Member"
    STAFF = "Staff"
    EVENTS_TEAM = "Events Team"
    RECRUITMENT_TEAM = "Recruitment Team"
    DISCORD_TEAM = "Discord Team"
    BOT_TEAM = "Bot Team"
    LEADERSHIP = "Leadership"

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

    @staticmethod
    def any():
        """Returns all roles in a list"""
        return list(ROLE)


def get_highest_privilage_role_from_member(member: discord.Member) -> Optional[ROLE]:
    matching_roles = [role for role in ROLE if ROLE.value in member.roles]
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
    required_roles = set([r.lower() for r in roles])
    actual_roles = set([r.name.lower() for r in member.roles])

    return len(required_roles & actual_roles) > 0
