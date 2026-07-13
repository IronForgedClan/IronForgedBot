from ironforgedcore.common.numbers import render_percentage


def build_rank_progress_bar(
    points_total: int,
    rank_point_threshold: int,
    next_rank_point_threshold: int,
    rank_icon: str,
    next_rank_icon: str,
) -> str:
    """Build a visual progress bar string showing progress toward the next rank.

    Args:
        points_total: The member's current score.
        rank_point_threshold: The point threshold for the current rank.
        next_rank_point_threshold: The point threshold for the next rank.
        rank_icon: Emoji for the current rank.
        next_rank_icon: Emoji for the next rank.
    """
    bar_length = 20
    filled_char = "▰"
    empty_char = "▱"
    span = next_rank_point_threshold - rank_point_threshold
    progress = points_total - rank_point_threshold
    ratio = max(0.0, min(1.0, progress / span)) if span > 0 else 1.0
    filled = round(ratio * bar_length)
    bar = filled_char * filled + empty_char * (bar_length - filled)
    percentage = render_percentage(progress, span)
    return f"{rank_icon} {bar} {next_rank_icon} ({percentage})"
