import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Union

from wom import GroupRole
from wom.models import GroupDetail, GroupMembership, GroupMemberGains, PlayerGains

from ironforgedbot.common.ranks import RANK, get_activity_threshold_for_rank
from ironforgedbot.common.roles import is_exempt_from_activity_check
from ironforgedbot.common.wom_role_mapping import (
    get_discord_role_for_wom_role,
    get_display_name_for_wom_role,
)

logger = logging.getLogger(__name__)


@dataclass
class ActivityCheckResult:
    """Result of checking a single member's activity against requirements.

    Attributes:
        username: Player's username
        wom_role: Player's WOM group role
        discord_role: Corresponding Discord role (from mapping)
        xp_gained: XP gained this month
        xp_threshold: Required XP/month for their rank
        is_active: True if member meets threshold
        is_exempt: True if member is exempt from activity checks
        is_absent: True if member is on absent list
        is_prospect: True if member is a prospect (Dogsbody)
        last_changed_at: When player last progressed in WOM
        check_timestamp: When this check was performed
        skip_reason: Why this member was skipped, if applicable
    """

    username: str
    wom_role: Optional[GroupRole]
    discord_role: Optional[str]
    xp_gained: int
    xp_threshold: int
    is_active: bool
    is_exempt: bool
    is_absent: bool
    is_prospect: bool
    last_changed_at: Optional[datetime]
    check_timestamp: datetime
    skip_reason: Optional[str] = None


def extract_overall_xp_gained(gains: Union[GroupMemberGains, PlayerGains]) -> float:
    """Extract overall XP gained from either bulk or individual gains data.

    Args:
        gains: Either GroupMemberGains (from bulk API) or PlayerGains (from individual API)

    Returns:
        Overall XP gained as a float
    """
    if isinstance(gains, GroupMemberGains):
        # Bulk API: gains.data.gained is directly the overall XP
        return gains.data.gained
    else:
        # Individual API: gains.data.skills is a dict, need to get Overall metric
        # PlayerGains.data is a PlayerGainsData object with .skills dict
        from wom import Metric

        overall_skill = gains.data.skills.get(Metric.Overall)
        if overall_skill:
            return overall_skill.experience.gained
        return 0.0


def find_member_in_group(
    group: GroupDetail, player_id: int
) -> Optional[GroupMembership]:
    """Find a member in a WOM group by player ID.

    Args:
        group: WOM group details
        player_id: Player ID to search for

    Returns:
        GroupMembership if found, None otherwise
    """
    for member in group.memberships:
        if member.player.id == player_id:
            return member
    return None


def check_member_activity(
    wom_username: str,
    wom_group: GroupDetail,
    monthly_gains: Union[GroupMemberGains, PlayerGains],
    absentees: List[str],
    member_rank: RANK,
) -> ActivityCheckResult:
    """Check a single member's activity against requirements.

    Args:
        wom_username: Player's WOM username
        wom_group: WOM group details containing membership info
        monthly_gains: Monthly gains data (from bulk or individual API)
        absentees: List of absent member usernames (lowercase)
        member_rank: Member's rank

    Returns:
        ActivityCheckResult with all check details
    """
    check_timestamp = datetime.now()

    if isinstance(monthly_gains, GroupMemberGains):
        player_id = monthly_gains.player.id
    else:
        player_membership = None
        for member in wom_group.memberships:
            if member.player.username.lower() == wom_username.lower():
                player_membership = member
                break

        if not player_membership:
            return ActivityCheckResult(
                username=wom_username,
                wom_role=None,
                discord_role=None,
                xp_gained=0,
                xp_threshold=0,
                is_active=False,
                is_exempt=False,
                is_absent=False,
                is_prospect=False,
                last_changed_at=None,
                check_timestamp=check_timestamp,
                skip_reason="not_in_group",
            )

        player_id = player_membership.player.id

    wom_member = find_member_in_group(wom_group, player_id)

    if wom_member is None:
        return ActivityCheckResult(
            username=wom_username,
            wom_role=None,
            discord_role=None,
            xp_gained=0,
            xp_threshold=0,
            is_active=False,
            is_exempt=False,
            is_absent=False,
            is_prospect=False,
            last_changed_at=None,
            check_timestamp=check_timestamp,
            skip_reason="not_in_group",
        )

    is_absent = wom_member.player.username.lower() in absentees
    is_prospect = wom_member.role == GroupRole.Dogsbody

    discord_role = get_discord_role_for_wom_role(wom_member.role)
    is_exempt = discord_role is not None and is_exempt_from_activity_check(discord_role)

    xp_threshold = get_activity_threshold_for_rank(member_rank)
    xp_gained = extract_overall_xp_gained(monthly_gains)

    is_active = xp_gained >= xp_threshold

    skip_reason = None
    if is_absent:
        skip_reason = "absent"
    elif is_exempt:
        skip_reason = "exempt"
    elif is_prospect:
        skip_reason = "prospect"

    last_changed_at = wom_member.player.last_changed_at

    return ActivityCheckResult(
        username=wom_member.player.username,
        wom_role=wom_member.role,
        discord_role=get_display_name_for_wom_role(wom_member.role),
        xp_gained=int(xp_gained),
        xp_threshold=xp_threshold,
        is_active=is_active,
        is_exempt=is_exempt,
        is_absent=is_absent,
        is_prospect=is_prospect,
        last_changed_at=last_changed_at,
        check_timestamp=check_timestamp,
        skip_reason=skip_reason,
    )


async def check_bulk_activity(
    wom_group: GroupDetail,
    all_member_gains: List[GroupMemberGains],
    absentees: List[str],
) -> List[ActivityCheckResult]:
    """Check activity for all members in bulk.

    Args:
        wom_group: WOM group details
        all_member_gains: List of all member gains from bulk API
        absentees: List of absent member usernames (lowercase)

    Returns:
        List of ActivityCheckResult for all members
    """
    from ironforgedbot.common.helpers import normalize_discord_string
    from ironforgedbot.database.database import db
    from ironforgedbot.services.service_factory import create_member_service

    results = []

    async with db.get_session() as session:
        member_service = create_member_service(session)

        for member_gains in all_member_gains:
            try:
                # Fetch member from database to get their rank
                db_member = await member_service.get_member_by_nickname(
                    normalize_discord_string(member_gains.player.username)
                )

                if not db_member:
                    logger.warning(
                        f"Member {member_gains.player.username} not found in database, skipping"
                    )
                    continue

                result = check_member_activity(
                    wom_username=member_gains.player.username,
                    wom_group=wom_group,
                    monthly_gains=member_gains,
                    absentees=absentees,
                    member_rank=db_member.rank,
                )
                results.append(result)
            except Exception as e:
                logger.warning(
                    f"Error checking activity for {getattr(member_gains.player, 'username', 'unknown')}: {e}"
                )

    return results
