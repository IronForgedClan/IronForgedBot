import discord
from tabulate import tabulate

from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LeaderboardConfig,
    LeaderboardEntry,
    StaffLeaderboardEntry,
)
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.text_formatters import text_code_block

_PAGE_SIZE = 20
_EMBED_TIMEOUT = 60


def _build_leaderboard_table(
    entries: list[LeaderboardEntry], config: LeaderboardConfig, page_offset: int
) -> str:
    """Build a table string for a single leaderboard page.

    Args:
        entries: The slice of entries for this page.
        config: The leaderboard configuration describing column headers and formatting.
        page_offset: The zero-based index of the first entry on this page, used to
            compute continuous rank numbers across pages.

    Returns:
        A markdown code-block string containing the formatted table.
    """
    rows = [
        (page_offset + i + 1, entry.nickname, config.value_formatter(entry))
        for i, entry in enumerate(entries)
    ]
    table = tabulate(
        rows,
        headers=["Rank", "Member", config.column_header],
        tablefmt="simple",
        colalign=("right", "left", "right"),
    )
    return text_code_block(table)


def _resolve_title(config: LeaderboardConfig) -> str:
    if config.emoji:
        icon = find_emoji(config.emoji)
        return f"{icon} {config.title}" if icon else config.title
    return config.title


def build_leaderboard_embeds(
    entries: list[LeaderboardEntry],
    config: LeaderboardConfig,
    page_size: int = _PAGE_SIZE,
) -> list[discord.Embed]:
    """Build one embed per page of leaderboard results.

    Args:
        entries: Full sorted entry list (descending by leaderboard metric).
        config: The leaderboard configuration.
        page_size: Number of entries per page.

    Returns:
        A list of discord.Embed objects, one per page. Returns a single embed
        with an empty-state message if entries is empty.
    """
    title = _resolve_title(config)
    if not entries:
        return [
            build_response_embed(
                title,
                f"{config.description}\n\nNo members found.",
                discord.Color.gold(),
            )
        ]

    pages = [entries[i : i + page_size] for i in range(0, len(entries), page_size)]
    total_pages = len(pages)
    embeds = []

    for page_idx, page in enumerate(pages):
        table = _build_leaderboard_table(page, config, page_offset=page_idx * page_size)
        parts = [f"{config.description}\n", table]
        if total_pages > 1:
            parts.append(f"-# _page {page_idx + 1} of {total_pages}_")
        embed = build_response_embed(
            title,
            "\n".join(parts),
            discord.Color.gold(),
        )
        embeds.append(embed)

    return embeds


def find_caller_page(
    entries: list[LeaderboardEntry],
    discord_id: int,
    page_size: int = _PAGE_SIZE,
) -> int | None:
    """Return the 1-indexed page number where the calling member appears.

    Args:
        entries: Full sorted entry list.
        discord_id: The discord_id of the calling user.
        page_size: Number of entries per page.

    Returns:
        1-indexed page number, or None if the member is not in the list.
    """
    for i, entry in enumerate(entries):
        if entry.discord_id == discord_id:
            return (i // page_size) + 1
    return None


def _build_staff_rank_block(
    rank: RANK,
    entries: list[StaffLeaderboardEntry],
    global_offset: int,
    column_header: str,
    value_formatter,
) -> str:
    """Build a rank subheading + table block for one rank group.

    Args:
        rank: The RANK being rendered.
        entries: The entries in this rank group, already sorted by score descending.
        global_offset: The zero-based global rank number of the first entry in this group.
        column_header: The column header string (e.g. "Score").
        value_formatter: Callable that formats an entry's value for display.

    Returns:
        A string containing a bold rank heading followed by a code-block table.
    """
    icon = find_emoji(str(rank))
    heading = f"**{icon} {rank}**" if icon else f"**{rank}**"

    rows = [
        (global_offset + i + 1, entry.nickname, value_formatter(entry))
        for i, entry in enumerate(entries)
    ]
    table = tabulate(
        rows,
        headers=["Rank", "Member", column_header],
        tablefmt="simple",
        colalign=("right", "left", "right"),
    )
    return f"{heading}\n{text_code_block(table)}"


def build_staff_leaderboard_embeds(
    entries: list[StaffLeaderboardEntry],
    config: LeaderboardConfig,
    page_size: int = _PAGE_SIZE,
) -> list[discord.Embed]:
    """Build paginated embeds for the staff leaderboard, grouped by rank.

    Entries are grouped by RANK in enum declaration order (highest first).
    Within each group they are sorted by score descending. Rank groups are
    never split across pages — if a group does not fit on the current page
    it starts a new one. Global rank numbers are continuous across all groups.

    Args:
        entries: Full unsorted list of staff leaderboard entries.
        config: The leaderboard configuration.
        page_size: Maximum number of entries per page.

    Returns:
        A list of discord.Embed objects, one per page. Returns a single embed
        with an empty-state message if entries is empty.
    """
    title = _resolve_title(config)

    if not entries:
        return [
            build_response_embed(
                title,
                f"{config.description}\n\nNo members found.",
                discord.Color.gold(),
            )
        ]

    rank_order = list(RANK)
    groups: list[tuple[RANK, list[StaffLeaderboardEntry]]] = []
    for rank in rank_order:
        group = sorted(
            [e for e in entries if e.rank == rank],
            key=lambda e: e.value,
            reverse=True,
        )
        if group:
            groups.append((rank, group))

    pages: list[list[str]] = []
    current_page_blocks: list[str] = []
    current_page_count = 0
    global_offset = 0

    for rank, group in groups:
        block = _build_staff_rank_block(
            rank, group, global_offset, config.column_header, config.value_formatter
        )
        group_size = len(group)

        if current_page_count + group_size > page_size and current_page_blocks:
            pages.append(current_page_blocks)
            current_page_blocks = []
            current_page_count = 0

        current_page_blocks.append(block)
        current_page_count += group_size
        global_offset += group_size

    if current_page_blocks:
        pages.append(current_page_blocks)

    total_pages = len(pages)
    embeds = []

    for page_idx, blocks in enumerate(pages):
        parts = [f"{config.description}\n"] + blocks
        if total_pages > 1:
            parts.append(f"-# _page {page_idx + 1} of {total_pages}_")
        embed = build_response_embed(
            title,
            "\n".join(parts),
            discord.Color.gold(),
        )
        embeds.append(embed)

    return embeds
