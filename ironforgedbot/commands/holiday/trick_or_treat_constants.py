"""Constants and configuration for the trick-or-treat Halloween event."""

from enum import Enum

# Ingot reward/deduction ranges
LOW_INGOT_MIN = 500
LOW_INGOT_MAX = 2_200
HIGH_INGOT_MIN = 3_200
HIGH_INGOT_MAX = 8_100
JACKPOT_VALUE = 1_000_000

# History limits
POSITIVE_MESSAGE_HISTORY_LIMIT = 10
NEGATIVE_MESSAGE_HISTORY_LIMIT = 10
THUMBNAIL_HISTORY_LIMIT = 15
GIF_HISTORY_LIMIT = 125


class TrickOrTreat(Enum):
    """Enum representing different trick-or-treat outcomes with their probability weights.

    Values represent relative weights (higher value = higher probability).
    Total weight: 1000
    """

    # fmt: off
    GIF = 330                      # 33.0% (1/3.0)
    REMOVE_INGOTS_LOW = 137        # 13.7% (1/7.3)
    ADD_INGOTS_LOW = 128           # 12.8% (1/7.8)
    REMOVE_INGOTS_HIGH = 119       # 11.9% (1/8.4)
    ADD_INGOTS_HIGH = 110          # 11.0% (1/9.1)
    DOUBLE_OR_NOTHING = 91         #  9.1% (1/11.0)
    STEAL = 46                     #  4.6% (1/21.7)
    JOKE = 18                      #  1.8% (1/55.6)
    REMOVE_ALL_INGOTS_TRICK = 18   #  1.8% (1/55.6)
    JACKPOT_INGOTS = 3             #  0.3% (1/333.3)
    # fmt: on
