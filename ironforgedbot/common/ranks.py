from strenum import StrEnum
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


def get_rank_from_points(points: int) -> str:
    if points >= 13000:
        return RANKS.MYTH
    if points >= 9000:
        return RANKS.LEGEND
    if points >= 5000:
        return RANKS.DRAGON
    if points >= 3000:
        return RANKS.RUNE
    if points >= 1500:
        return RANKS.ADAMANT
    if points >= 700:
        return RANKS.MITHRIL
    return RANKS.IRON

def get_rank_color_from_points(points: int) -> Color:
    if points >= 13000:
        return Color.from_str("#0ecea9")
    if points >= 9000:
        return Color.from_str("#cecece")
    if points >= 5000:
        return Color.from_str("#a51c1c")
    if points >= 3000:
        return Color.from_str("#11b9f8")
    if points >= 1500:
        return Color.from_str("#25964f")
    if points >= 700:
        return Color.from_str("#7f54fc")
    return Color.from_str("#707070")

