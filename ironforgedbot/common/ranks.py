from strenum import StrEnum
from enum import IntEnum
from discord import Color


class RANKS(StrEnum):
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
    MYTH = 13_000
    LEGEND = 9_000
    DRAGON = 5_000
    RUNE = 3_000
    ADAMANT = 1_500
    MITHRIL = 700
    IRON = 0


def get_rank_from_points(points: int) -> str:
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
    if points >= RANK_POINTS.MYTH:
        return RANKS.MYTH
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


def get_rank_color_from_points(points: int) -> Color:
    rank = get_rank_from_points(points)

    if rank == RANKS.MYTH:
        return Color.from_str("#0ecea9")

    if rank == RANKS.LEGEND:
        return Color.from_str("#cecece")

    if rank == RANKS.DRAGON:
        return Color.from_str("#a51c1c")

    if rank == RANKS.RUNE:
        return Color.from_str("#11b9f8")

    if rank == RANKS.ADAMANT:
        return Color.from_str("#25964f")

    if rank == RANKS.MITHRIL:
        return Color.from_str("#7f54fc")

    return Color.from_str("#707070")
