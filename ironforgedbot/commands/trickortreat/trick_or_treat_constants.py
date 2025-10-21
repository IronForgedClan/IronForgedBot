import logging
import yaml
from enum import Enum

logger = logging.getLogger(__name__)

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

REQUIRED_OUTCOMES = {
    "GIF",
    "REMOVE_INGOTS_LOW",
    "REMOVE_INGOTS_HIGH",
    "ADD_INGOTS_LOW",
    "ADD_INGOTS_HIGH",
    "QUIZ_MASTER",
    "DOUBLE_OR_NOTHING",
    "STEAL",
    "JOKE",
    "BACKROOMS",
    "REMOVE_ALL_INGOTS_TRICK",
    "JACKPOT_INGOTS",
}

EXPECTED_TOTAL_WEIGHT = 1000


def _validate_weights(weights: dict) -> None:
    """Validate trick-or-treat outcome weights.

    Args:
        weights: Dictionary mapping outcome names to weight values.

    Raises:
        ValueError: If validation fails for any reason.
        TypeError: If weight values are not integers.
    """
    missing = REQUIRED_OUTCOMES - weights.keys()
    if missing:
        raise ValueError(
            f"Missing required outcomes in weights file: {sorted(missing)}"
        )

    extra = set(weights.keys()) - REQUIRED_OUTCOMES
    if extra:
        logger.warning(
            f"Unexpected outcomes in weights file (will be ignored): {sorted(extra)}"
        )

    non_integers = {
        name: value for name, value in weights.items() if not isinstance(value, int)
    }
    if non_integers:
        raise TypeError(
            f"All weights must be integers, found non-integers: {non_integers}"
        )

    invalid_weights = {name: value for name, value in weights.items() if value <= 0}
    if invalid_weights:
        raise ValueError(
            f"All weights must be positive (> 0), found invalid: {invalid_weights}"
        )

    weight_values = list(weights.values())
    duplicates = {
        value: [name for name, w in weights.items() if w == value]
        for value in weight_values
        if weight_values.count(value) > 1
    }
    if duplicates:
        duplicate_info = {
            value: names for value, names in duplicates.items() if len(names) > 1
        }
        raise ValueError(
            f"Duplicate weight values create enum aliases: {duplicate_info}. "
            "All weights must be unique."
        )

    total = sum(weights.values())
    if total != EXPECTED_TOTAL_WEIGHT:
        raise ValueError(
            f"Total weight must be {EXPECTED_TOTAL_WEIGHT} (base-1000), "
            f"but got {total}. Difference: {total - EXPECTED_TOTAL_WEIGHT}"
        )


try:
    with open("data/trick_or_treat_weights.yaml") as f:
        _weights = yaml.safe_load(f)
except FileNotFoundError as e:
    raise FileNotFoundError(
        f"Trick-or-treat weights file not found: {e.filename}. "
        "Expected file at: data/trick_or_treat_weights.yaml"
    ) from e
except yaml.YAMLError as e:
    raise ValueError(f"Invalid YAML syntax in trick-or-treat weights file: {e}") from e
except Exception as e:
    raise RuntimeError(f"Unexpected error loading trick-or-treat weights: {e}") from e

_validate_weights(_weights)

TrickOrTreat = Enum("TrickOrTreat", _weights)
