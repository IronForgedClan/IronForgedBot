import logging
from typing import Optional
import discord
from strenum import StrEnum
from enum import IntEnum
from discord import Color


class RANKS(StrEnum):
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
    GOD = 20_000
    MYTH = 13_000
    LEGEND = 9_000
    DRAGON = 5_000
    RUNE = 3_000
    ADAMANT = 1_500
    MITHRIL = 700
    IRON = 0


class GOD_ALIGNMENT(StrEnum):
    SARADOMIN = "Saradominist"
    GUTHIX = "Guthixian"
    ZAMORAK = "Zamorakian"


def get_rank_from_points(points: int) -> str:
    if points >= RANK_POINTS.GOD:
        return RANKS.GOD
    if points >= RANK_POINTS.MYTH:
        return RANKS.MYTH
    if points >= RANK_POINTS.LEGEND:
        return RANKS.LEGEND
    if points >= RANK_POINTS.DRAGON:
        return RANKS.DRAGON
    if points >= RANK_POINTS.RUNE:
        return RANKS.RUNE
    if points >= RANK_POINTS.ADAMANT:
        return RANKS.ADAMANT
    if points >= RANK_POINTS.MITHRIL:
        return RANKS.MITHRIL
    return RANKS.IRON


# TODO: Probably a more elegant way to achieve this using RANK_POINTS enum
def get_next_rank_from_points(points: int) -> str:
    if points >= RANK_POINTS.GOD:
        return RANKS.GOD
    if points >= RANK_POINTS.MYTH:
        return RANKS.GOD
    if points >= RANK_POINTS.LEGEND:
        return RANKS.MYTH
    if points >= RANK_POINTS.DRAGON:
        return RANKS.LEGEND
    if points >= RANK_POINTS.RUNE:
        return RANKS.DRAGON
    if points >= RANK_POINTS.ADAMANT:
        return RANKS.RUNE
    if points >= RANK_POINTS.MITHRIL:
        return RANKS.ADAMANT
    return RANKS.MITHRIL


def get_rank_color_from_points(
    points: int, god_alignment: Optional[str] = None
) -> Color:
    rank = get_rank_from_points(points)

    if rank == RANKS.GOD:
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
        case RANKS.MYTH:
            return Color.from_str("#0ECEA9")
        case RANKS.LEGEND:
            return Color.from_str("#CECECE")
        case RANKS.DRAGON:
            return Color.from_str("#A51C1C")
        case RANKS.RUNE:
            return Color.from_str("#11B9F8")
        case RANKS.ADAMANT:
            return Color.from_str("#25964F")
        case RANKS.MITHRIL:
            return Color.from_str("#7F54FC")
        case _:
            return Color.from_str("#707070")


def get_god_alignment_from_member(member: discord.Member) -> str | None:
    for role in member.roles:
        logging.info(f"checking role: {role}")
        match role.name:
            case GOD_ALIGNMENT.SARADOMIN:
                return role.name
            case GOD_ALIGNMENT.ZAMORAK:
                return role.name
            case GOD_ALIGNMENT.GUTHIX:
                return role.name

    return None
