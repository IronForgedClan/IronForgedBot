"""Discord-coupled rank helpers. RANK enum lives in ironforgedcore.common.ranks."""

from typing import Optional

import discord
from discord import Color

from ironforgedcore.common.ranks import GOD_ALIGNMENT, RANK


def get_rank_from_member(member: discord.Member | None) -> RANK | str | None:
    if not member:
        return None

    member_role_names = {r.name for r in member.roles}

    for rank in RANK:
        if rank.value in member_role_names:
            if rank == RANK.GOD:
                alignment = get_god_alignment_from_member(member)
                return alignment if alignment else RANK.GOD
            return rank

    return None


def get_rank_color_from_points(
    points: int, god_alignment: Optional[str] = None
) -> Color:
    from ironforgedcore.common.ranks import get_rank_from_points

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
