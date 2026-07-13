from enum import IntEnum
from strenum import StrEnum


class RANK(StrEnum):
    GOD_ZAMORAK = "God_Zamorak"
    GOD_GUTHIX = "God_Guthix"
    GOD_SARADOMIN = "God_Saradomin"
    GOD = "God"
    MYTH = "Myth"
    LEGEND = "Legend"
    DRAGON = "Dragon"
    RUNE = "Rune"
    ADAMANT = "Adamant"
    MITHRIL = "Mithril"
    IRON = "Iron"

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class RANK_POINTS(IntEnum):
    GOD_ZAMORAK = 20_000
    GOD_GUTHIX = 20_000
    GOD_SARADOMIN = 20_000
    GOD = 20_000
    MYTH = 13_000
    LEGEND = 9_000
    DRAGON = 5_000
    RUNE = 3_000
    ADAMANT = 1_500
    MITHRIL = 700
    IRON = 0


class RANK_ACTIVITY_THRESHOLDS(IntEnum):
    """Monthly XP thresholds for activity checks based on achievement rank."""

    GOD_ZAMORAK = 500_000
    GOD_GUTHIX = 500_000
    GOD_SARADOMIN = 500_000
    GOD = 500_000
    MYTH = 500_000
    LEGEND = 500_000
    DRAGON = 500_000
    RUNE = 500_000
    ADAMANT = 300_000
    MITHRIL = 300_000
    IRON = 150_000


class GOD_ALIGNMENT(StrEnum):
    SARADOMIN = "Saradominist"
    GUTHIX = "Guthixian"
    ZAMORAK = "Zamorakian"

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


def get_rank_from_points(points: int) -> str:
    if points >= RANK_POINTS.GOD:
        return RANK.GOD
    if points >= RANK_POINTS.MYTH:
        return RANK.MYTH
    if points >= RANK_POINTS.LEGEND:
        return RANK.LEGEND
    if points >= RANK_POINTS.DRAGON:
        return RANK.DRAGON
    if points >= RANK_POINTS.RUNE:
        return RANK.RUNE
    if points >= RANK_POINTS.ADAMANT:
        return RANK.ADAMANT
    if points >= RANK_POINTS.MITHRIL:
        return RANK.MITHRIL
    return RANK.IRON


def get_next_rank_from_points(points: int) -> str:
    if points >= RANK_POINTS.GOD:
        return RANK.GOD
    if points >= RANK_POINTS.MYTH:
        return RANK.GOD
    if points >= RANK_POINTS.LEGEND:
        return RANK.MYTH
    if points >= RANK_POINTS.DRAGON:
        return RANK.LEGEND
    if points >= RANK_POINTS.RUNE:
        return RANK.DRAGON
    if points >= RANK_POINTS.ADAMANT:
        return RANK.RUNE
    if points >= RANK_POINTS.MITHRIL:
        return RANK.ADAMANT
    return RANK.MITHRIL


def get_activity_threshold_for_rank(rank: RANK) -> int:
    """
    Get the monthly XP activity threshold for a given rank.

    Args:
        rank: Achievement rank

    Returns:
        Monthly XP threshold for activity checks
    """
    try:
        return RANK_ACTIVITY_THRESHOLDS[rank.name]
    except KeyError:
        return RANK_ACTIVITY_THRESHOLDS.GOD
