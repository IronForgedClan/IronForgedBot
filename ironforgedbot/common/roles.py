from enum import StrEnum
from typing import Optional

import discord


class ROLE(StrEnum):
    GUEST = "Guest"
    APPLICANT = "Applicant"
    PROSPECT = "Prospect"
    MEMBER = "Member"
    STAFF = "Staff"
    EVENTS_TEAM = "Events Team"
    RECRUITMENT_TEAM = "Recruitment Team"
    DISCORD_TEAM = "Discord Team"
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
