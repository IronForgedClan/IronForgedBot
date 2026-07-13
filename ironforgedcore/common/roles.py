from enum import StrEnum


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
