"""Constants and configuration for the trick-or-treat Halloween event."""

from enum import Enum

# Ingot reward/deduction ranges
LOW_INGOT_MIN = 300
LOW_INGOT_MAX = 1_800
HIGH_INGOT_MIN = 2_200
HIGH_INGOT_MAX = 6_100
JACKPOT_VALUE = 1_000_000

# Backrooms configuration
BACKROOMS_DOOR_COUNT = 3
BACKROOMS_TREASURE_MIN = HIGH_INGOT_MIN
BACKROOMS_TREASURE_MAX = HIGH_INGOT_MAX
BACKROOMS_MONSTER_MIN = HIGH_INGOT_MIN
BACKROOMS_MONSTER_MAX = HIGH_INGOT_MAX

# Quiz Master configuration
QUIZ_CORRECT_MIN = 2_000
QUIZ_CORRECT_MAX = 7_000
QUIZ_WRONG_PENALTY_MIN = 1_000
QUIZ_WRONG_PENALTY_MAX = 3_500
QUIZ_PENALTY_CHANCE = 0.7

# History limits
POSITIVE_MESSAGE_HISTORY_LIMIT = 15
NEGATIVE_MESSAGE_HISTORY_LIMIT = 15
THUMBNAIL_HISTORY_LIMIT = 25
GIF_HISTORY_LIMIT = 125


class TrickOrTreat(Enum):
    """Enum representing different trick-or-treat outcomes with their probability weights.

    Values represent relative weights (higher value = higher probability).
    Total weight: 1035
    """

    # fmt: off
    GIF = 305                      # 29.5% (1/3.4)
    REMOVE_INGOTS_LOW = 137        # 13.2% (1/7.6)
    ADD_INGOTS_LOW = 128           # 12.4% (1/8.1)
    REMOVE_INGOTS_HIGH = 119       # 11.5% (1/8.7)
    ADD_INGOTS_HIGH = 110          # 10.6% (1/9.4)
    DOUBLE_OR_NOTHING = 91         #  8.8% (1/11.4)
    STEAL = 46                     #  4.4% (1/22.5)
    QUIZ_MASTER = 35               #  3.4% (1/29.6)
    BACKROOMS = 25                 #  2.4% (1/41.4)
    JOKE = 18                      #  1.7% (1/57.5)
    REMOVE_ALL_INGOTS_TRICK = 18   #  1.7% (1/57.5)
    JACKPOT_INGOTS = 3             #  0.3% (1/345.0)
    # fmt: on
