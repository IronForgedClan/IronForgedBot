from typing import Dict, Optional
from wom import GroupRole

from ironforgedbot.common.ranks import RANK, get_activity_threshold_for_rank
from ironforgedbot.common.roles import ROLE


WOM_TO_DISCORD_ROLE_MAPPING: Dict[GroupRole, ROLE] = {
    # Prospect
    GroupRole.Dogsbody: ROLE.PROSPECT,
    # Member roles
    GroupRole.Iron: ROLE.MEMBER,
    GroupRole.Mithril: ROLE.MEMBER,
    GroupRole.Adamant: ROLE.MEMBER,
    GroupRole.Rune: ROLE.MEMBER,
    GroupRole.Dragon: ROLE.MEMBER,
    GroupRole.Legend: ROLE.MEMBER,
    GroupRole.Myth: ROLE.MEMBER,
    # God alignment roles
    GroupRole.Sage: ROLE.MEMBER,
    GroupRole.Destroyer: ROLE.MEMBER,
    GroupRole.Mediator: ROLE.MEMBER,
    # Staff roles
    GroupRole.Collector: ROLE.STAFF,
    GroupRole.Colonel: ROLE.STAFF,
    GroupRole.Brigadier: ROLE.STAFF,
    GroupRole.Helper: ROLE.STAFF,
    # Leadership roles
    GroupRole.Admiral: ROLE.LEADERSHIP,
    GroupRole.Marshal: ROLE.LEADERSHIP,
    GroupRole.Deputy_owner: ROLE.LEADERSHIP,
    GroupRole.Owner: ROLE.LEADERSHIP,
    GroupRole.Administrator: ROLE.LEADERSHIP,
}

WOM_TO_DISCORD_RANK_MAPPING: Dict[GroupRole, RANK] = {
    # Achievement-based rank mapping
    GroupRole.Iron: RANK.IRON,
    GroupRole.Mithril: RANK.MITHRIL,
    GroupRole.Adamant: RANK.ADAMANT,
    GroupRole.Rune: RANK.RUNE,
    GroupRole.Dragon: RANK.DRAGON,
    GroupRole.Legend: RANK.LEGEND,
    GroupRole.Myth: RANK.MYTH,
    # God alignment roles map to GOD rank with alignment
    GroupRole.Sage: RANK.GOD_GUTHIX,
    GroupRole.Destroyer: RANK.GOD_ZAMORAK,
    GroupRole.Mediator: RANK.GOD_SARADOMIN,
    # Staff/leadership roles have no specific rank mappings
}


def get_discord_rank_for_wom_role(wom_role: Optional[GroupRole]) -> Optional[RANK]:
    """
    Get the Discord achievement rank that corresponds to a WOM role.

    Args:
        wom_role: WiseOldMan GroupRole enum value

    Returns:
        Corresponding Discord RANK enum value, or None if no mapping exists
    """
    if wom_role is None:
        return None

    return WOM_TO_DISCORD_RANK_MAPPING.get(wom_role)


def get_discord_role_for_wom_role(wom_role: Optional[GroupRole]) -> Optional[ROLE]:
    """
    Get the Discord role that corresponds to a WOM role.

    Args:
        wom_role: WiseOldMan GroupRole enum value

    Returns:
        Corresponding Discord ROLE enum value, or None if no mapping exists
    """
    if wom_role is None:
        return None

    return WOM_TO_DISCORD_ROLE_MAPPING.get(wom_role)


def get_threshold_for_wom_role(wom_role: Optional[GroupRole]) -> int:
    """
    Get the activity threshold for a WOM role based on its Discord rank mapping.

    Args:
        wom_role: WiseOldMan GroupRole enum value

    Returns:
        XP threshold for the role. Returns highest threshold if role not mapped.
    """
    if wom_role is None:
        return 0

    discord_rank = get_discord_rank_for_wom_role(wom_role)
    if discord_rank is None:
        print("unknown discord rank")
        return 0

    return get_activity_threshold_for_rank(discord_rank)


def get_display_name_for_wom_role(wom_role: Optional[GroupRole]) -> str:
    """
    Get display name for a WOM role based on its Discord role mapping.

    Args:
        wom_role: WiseOldMan GroupRole enum value

    Returns:
        Human-readable role name for display purposes
    """
    if wom_role is None:
        return "Unknown"

    discord_role = get_discord_role_for_wom_role(wom_role)
    if discord_role is None:
        return str(wom_role).replace("_", " ").title()

    return discord_role.value
