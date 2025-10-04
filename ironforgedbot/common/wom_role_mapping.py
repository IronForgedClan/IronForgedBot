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
    # Staff/leadership roles have no specific rank mapping (None handled separately)
    # These are permission-based roles, not achievement ranks
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
        # Unknown roles get the highest threshold (most strict) - use GOD threshold
        return get_activity_threshold_for_rank(RANK.GOD)

    # Get the corresponding Discord rank
    discord_rank = get_discord_rank_for_wom_role(wom_role)

    if discord_rank is None:
        # Unmapped WOM roles get the highest threshold (most strict) - use GOD threshold
        return get_activity_threshold_for_rank(RANK.GOD)

    # Return the threshold for the Discord rank
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
        # For unmapped roles, use the WOM role name with title case
        return str(wom_role).replace("_", " ").title()

    # Use Discord role name for mapped roles
    return discord_role.value


def get_all_wom_roles_for_discord_role(discord_role: ROLE) -> list[GroupRole]:
    """
    Get all WOM roles that map to a specific Discord role.

    Args:
        discord_role: Discord ROLE enum value

    Returns:
        List of WOM GroupRole values that map to the Discord role
    """
    return [
        wom_role
        for wom_role, mapped_role in WOM_TO_DISCORD_ROLE_MAPPING.items()
        if mapped_role == discord_role
    ]


def get_all_wom_roles_for_discord_rank(discord_rank: RANK) -> list[GroupRole]:
    """
    Get all WOM roles that map to a specific Discord rank.

    Args:
        discord_rank: Discord RANK enum value

    Returns:
        List of WOM GroupRole values that map to the Discord rank
    """
    return [
        wom_role
        for wom_role, mapped_rank in WOM_TO_DISCORD_RANK_MAPPING.items()
        if mapped_rank == discord_rank
    ]


def validate_role_mappings() -> list[str]:
    """
    Validate the role mapping configuration for consistency.

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Validate that WOM roles map to valid ranks
    mapped_discord_ranks = set(WOM_TO_DISCORD_RANK_MAPPING.values())
    valid_ranks = set(RANK)

    invalid_ranks = mapped_discord_ranks - valid_ranks
    if invalid_ranks:
        errors.append(f"Invalid ranks in mapping: {invalid_ranks}")

    # Validate that WOM roles map to valid roles
    mapped_discord_roles = set(WOM_TO_DISCORD_ROLE_MAPPING.values())
    valid_roles = set(ROLE)

    invalid_roles = mapped_discord_roles - valid_roles
    if invalid_roles:
        errors.append(f"Invalid roles in mapping: {invalid_roles}")

    # Check that achievement ranks have valid thresholds
    for rank in mapped_discord_ranks:
        try:
            threshold = get_activity_threshold_for_rank(rank)
            if threshold < 0:
                errors.append(f"Negative threshold for rank {rank}: {threshold}")
        except Exception as e:
            errors.append(f"Error getting threshold for rank {rank}: {e}")

    return errors
