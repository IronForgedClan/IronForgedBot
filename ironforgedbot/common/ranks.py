from strenum import StrEnum


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


def get_rank_from_points(points: int):
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
