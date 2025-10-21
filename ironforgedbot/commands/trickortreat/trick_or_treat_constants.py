"""Constants and configuration for the trick-or-treat Halloween event."""

import yaml
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


# Load outcome weights from data file
with open("data/trick_or_treat_weights.yaml") as f:
    _weights = yaml.safe_load(f)

# Create TrickOrTreat enum dynamically from weights
TrickOrTreat = Enum("TrickOrTreat", _weights)
