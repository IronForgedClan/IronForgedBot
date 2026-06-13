from ironforgedbot.commands.leaderboard.leaderboard_ingots import INGOTS_LEADERBOARD
from ironforgedbot.commands.leaderboard.leaderboard_score import SCORE_LEADERBOARD
from ironforgedbot.commands.leaderboard.leaderboard_staff import STAFF_LEADERBOARD
from ironforgedbot.commands.leaderboard.leaderboard_types import LeaderboardConfig

LEADERBOARD_TYPES: dict[str, LeaderboardConfig] = {
    "ingots": INGOTS_LEADERBOARD,
    "score": SCORE_LEADERBOARD,
    "staff": STAFF_LEADERBOARD,
}
