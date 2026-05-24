import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Union

from wom import GroupRole
from wom.models import (
    GroupDetail,
    GroupMembership,
    GroupMemberGains,
    PlayerGains,
    SnapshotTimelineEntry,
)

from ironforgedbot.common.helpers import normalize_rsn
from ironforgedbot.common.ranks import RANK, get_activity_threshold_for_rank
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
    username: str,
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
        absentees: List of absent member nicknames normalized with normalize_rsn
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
            if member.player.username.lower() == normalize_rsn(username):
                player_membership = member
                break

        if not player_membership:
            return ActivityCheckResult(
                username=username,
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
            username=username,
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

    is_absent = normalize_rsn(wom_member.player.username) in absentees
    is_prospect = wom_member.role == GroupRole.Dogsbody

    # TODO: remove flag, prospects are now handled by is_prospect flag
    is_exempt = False

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


def build_daily_gains(
    snapshots: List[SnapshotTimelineEntry],
) -> List[tuple[datetime, int]]:
    """Convert a snapshot timeline into per-day XP gains, oldest to newest.

    Groups absolute XP snapshots by UTC day (taking the highest value per day),
    fills any gap days by carrying the previous day's value forward (0 gain for
    that day), then diffs consecutive days to produce gains. The first day in the
    window always has a gain of 0 because there is no prior snapshot to diff
    against.

    Args:
        snapshots: List of SnapshotTimelineEntry with absolute overall XP values
                   and timestamps. May be unsorted. May contain multiple entries
                   per day.

    Returns:
        Ordered list of (datetime, xp_gained) tuples, one per day in the window,
        oldest first. Returns an empty list if fewer than 2 snapshots are provided
        (insufficient to calculate any gain).
    """
    if len(snapshots) < 2:
        return []

    sorted_snapshots = sorted(snapshots, key=lambda s: s.date)

    # Group by UTC day, keeping the highest XP value seen that day.
    daily_max: Dict[datetime, int] = defaultdict(int)
    for entry in sorted_snapshots:
        day = entry.date.replace(hour=0, minute=0, second=0, microsecond=0)
        if entry.value > daily_max[day]:
            daily_max[day] = entry.value

    ordered_days = sorted(daily_max.keys())
    if not ordered_days:
        return []

    # Fill gaps: days between the first and last snapshot day that have no
    # snapshot carry the previous day's absolute XP value (implying 0 gain).
    filled: List[tuple[datetime, int]] = []
    current_day = ordered_days[0]
    last_value = daily_max[current_day]
    end_day = ordered_days[-1]

    while current_day <= end_day:
        if current_day in daily_max:
            last_value = daily_max[current_day]
        filled.append((current_day, last_value))
        current_day += timedelta(days=1)

    # Diff consecutive days to get per-day gains.
    # The first day is diffed against the very first snapshot's absolute XP value
    # (the baseline), so any XP gained within that first day is captured.
    # All subsequent days are diffed against the previous day's max value.
    baseline = sorted_snapshots[0].value
    daily_gains: List[tuple[datetime, int]] = []
    for i, (day, value) in enumerate(filled):
        if i == 0:
            gain = max(0, value - baseline)
        else:
            gain = max(0, value - filled[i - 1][1])
        daily_gains.append((day, gain))

    return daily_gains


def calculate_days_of_buffer(
    snapshots: List[SnapshotTimelineEntry],
    xp_threshold: int,
) -> int | None:
    """Calculate how many days a member can gain 0 XP before falling below threshold.

    Uses snapshot timeline data (absolute XP values at points in time) to
    reconstruct daily XP gains over the rolling 30-day window. Simulates
    the window advancing day by day, with each step dropping the oldest
    day's gains from the total, to find the first day the total falls below
    the threshold.

    Args:
        snapshots: Ordered list of SnapshotTimelineEntry for the past month.
                   Each entry has an absolute overall XP value and a date.
        xp_threshold: XP required per rolling month to be considered active.

    Returns:
        Number of days (>= 0) the member can sustain 0 XP before dropping
        below the threshold, or None if the calculation cannot be performed
        (e.g. fewer than 2 snapshots).
    """
    daily_gains = build_daily_gains(snapshots)
    if not daily_gains:
        return None

    total_xp = sum(g for _, g in daily_gains)

    # Simulate the window rolling forward one day at a time.
    # Each iteration: the oldest day drops off, and the new day contributes 0 xp.
    # Count how many days until total < threshold.
    gains_deque = list(daily_gains)
    days_safe = 0

    for _ in range(30):
        dropped_gain = gains_deque.pop(0)[1]
        total_xp -= dropped_gain
        gains_deque.append((datetime.now(tz=timezone.utc), 0))

        if total_xp < xp_threshold:
            break

        days_safe += 1

    return days_safe


async def check_bulk_activity(
    wom_group: GroupDetail,
    all_member_gains: List[GroupMemberGains],
    absentees: List[str],
) -> List[ActivityCheckResult]:
    """Check activity for all members in bulk.

    Args:
        wom_group: WOM group details
        all_member_gains: List of all member gains from bulk API
        absentees: List of absent member nicknames normalized with normalize_rsn

    Returns:
        List of ActivityCheckResult for all members
    """
    from ironforgedbot.database.database import db
    from ironforgedbot.services.service_factory import create_member_service

    results = []

    async with db.get_session() as session:
        member_service = create_member_service(session)

        for member_gains in all_member_gains:
            try:
                # Fetch member from database to get their rank
                db_member = await member_service.get_member_by_rsn(
                    member_gains.player.username
                )

                if not db_member:
                    logger.warning(
                        f"Member {member_gains.player.username} not found in database, skipping"
                    )
                    continue

                result = check_member_activity(
                    username=member_gains.player.username,
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
