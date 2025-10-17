"""Constants and configuration for the trick-or-treat Halloween event."""

from enum import Enum

# Ingot reward/deduction ranges
LOW_INGOT_MIN = 1_000
LOW_INGOT_MAX = 2_500
HIGH_INGOT_MIN = 3_000
HIGH_INGOT_MAX = 6_000
JACKPOT_VALUE = 1_000_000

# Backrooms configuration
BACKROOMS_DOOR_COUNT = 3
BACKROOMS_TREASURE_MIN = HIGH_INGOT_MIN + 2_000
BACKROOMS_TREASURE_MAX = HIGH_INGOT_MAX + 2_000
BACKROOMS_MONSTER_MIN = LOW_INGOT_MIN + 1_000
BACKROOMS_MONSTER_MAX = LOW_INGOT_MAX + 1_000

# Quiz Master configuration
QUIZ_CORRECT_MIN = HIGH_INGOT_MIN + 1_000
QUIZ_CORRECT_MAX = HIGH_INGOT_MAX + 2_500
QUIZ_WRONG_PENALTY_MIN = HIGH_INGOT_MIN + 1_000
QUIZ_WRONG_PENALTY_MAX = HIGH_INGOT_MAX + 2_000
QUIZ_PENALTY_CHANCE = 0.75

# History limits
POSITIVE_MESSAGE_HISTORY_LIMIT = 15
NEGATIVE_MESSAGE_HISTORY_LIMIT = 15
THUMBNAIL_HISTORY_LIMIT = 25
GIF_HISTORY_LIMIT = 125
QUIZ_QUESTION_HISTORY_LIMIT = 15


class TrickOrTreat(Enum):
    """Enum representing different trick-or-treat outcomes with their probability weights.

    Values represent relative weights (higher value = higher probability).
    Total weight: 1500
    """

    # fmt: off
    GIF = 526                      # 35.1% (1/2.9)
    REMOVE_INGOTS_LOW = 180        # 12.0% (1/8.3)
    REMOVE_INGOTS_HIGH = 170       # 11.3% (1/8.8)
    ADD_INGOTS_LOW = 150           # 10.0% (1/10.0)
    ADD_INGOTS_HIGH = 130          #  8.7% (1/11.5)
    QUIZ_MASTER = 130              #  8.7% (1/11.5)
    DOUBLE_OR_NOTHING = 80         #  5.3% (1/18.8)
    STEAL = 50                     #  3.3% (1/30.0)
    JOKE = 40                      #  2.7% (1/37.5)
    REMOVE_ALL_INGOTS_TRICK = 20   #  1.3% (1/75.0)
    BACKROOMS = 20                 #  1.3% (1/75.0)
    JACKPOT_INGOTS = 4             #  0.3% (1/375.0)
    # fmt: on
