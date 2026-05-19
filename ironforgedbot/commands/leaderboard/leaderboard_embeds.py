import discord
from tabulate import tabulate

from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LeaderboardConfig,
    LeaderboardEntry,
)
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.text_formatters import text_code_block

_PAGE_SIZE = 20
_EMBED_TIMEOUT = 60


def _build_leaderboard_table(
    entries: list[LeaderboardEntry], config: LeaderboardConfig, page_offset: int
) -> str:
    """Build a github-style table string for a single leaderboard page.

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
        headers=["Rank", "Player", config.column_header],
        tablefmt="github",
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
                title, f"{config.description}\n\nNo members found.", None
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
            None,
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
