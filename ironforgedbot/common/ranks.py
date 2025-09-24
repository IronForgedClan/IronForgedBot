from enum import IntEnum
from typing import Optional

import discord
from discord import Color
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
    MYTH = 400_000
    LEGEND = 350_000
    DRAGON = 300_000
    RUNE = 250_000
    ADAMANT = 200_000
    MITHRIL = 150_000
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


def get_rank_from_member(member: discord.Member | None) -> RANK | str | None:
    if not member:
        return None

    for role in member.roles:
        match role.name:
            case RANK.IRON:
                return RANK.IRON
            case RANK.MITHRIL:
                return RANK.MITHRIL
            case RANK.ADAMANT:
                return RANK.ADAMANT
            case RANK.RUNE:
                return RANK.RUNE
            case RANK.DRAGON:
                return RANK.DRAGON
            case RANK.LEGEND:
                return RANK.LEGEND
            case RANK.MYTH:
                return RANK.MYTH
            case RANK.GOD:
                alignment = get_god_alignment_from_member(member)
                return alignment if alignment else RANK.GOD

    return None


# TODO: Probably a more elegant way to achieve this using RANK_POINTS enum
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


def get_rank_color_from_points(
    points: int, god_alignment: Optional[str] = None
) -> Color:
    rank = get_rank_from_points(points)

    if rank == RANK.GOD:
        match god_alignment:
            case GOD_ALIGNMENT.SARADOMIN:
                return Color.from_str("#2F2BFF")
            case GOD_ALIGNMENT.ZAMORAK:
                return Color.from_str("#F80101")
            case GOD_ALIGNMENT.GUTHIX:
                return Color.from_str("#2ECC71")
            case _:
                return Color.from_str("#FFFFFF")

    match rank:
        case RANK.MYTH:
            return Color.from_str("#0ECEA9")
        case RANK.LEGEND:
            return Color.from_str("#CECECE")
        case RANK.DRAGON:
            return Color.from_str("#A51C1C")
        case RANK.RUNE:
            return Color.from_str("#11B9F8")
        case RANK.ADAMANT:
            return Color.from_str("#25964F")
        case RANK.MITHRIL:
            return Color.from_str("#7F54FC")
        case _:
            return Color.from_str("#707070")


def get_god_alignment_from_member(member: discord.Member | None) -> str | None:
    if not member:
        return None

    for role in member.roles:
        match role.name:
            case GOD_ALIGNMENT.SARADOMIN:
                return role.name
            case GOD_ALIGNMENT.ZAMORAK:
                return role.name
            case GOD_ALIGNMENT.GUTHIX:
                return role.name

    return None


def get_activity_threshold_for_rank(rank: RANK) -> int:
    """
    Get the monthly XP activity threshold for a given rank.

    Args:
        rank: Achievement rank

    Returns:
        Monthly XP threshold for activity checks
    """
    # Try to get the threshold using the rank name
    try:
        return RANK_ACTIVITY_THRESHOLDS[rank.name]
    except KeyError:
        # Default to Iron threshold for unknown ranks
        return RANK_ACTIVITY_THRESHOLDS.IRON
