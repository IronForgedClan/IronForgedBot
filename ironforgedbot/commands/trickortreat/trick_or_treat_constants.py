import logging
import yaml
from enum import Enum

logger = logging.getLogger(__name__)

TRICK_OR_TREAT_DATA_DIR = "data/trick_or_treat"
VALUES_FILE = f"{TRICK_OR_TREAT_DATA_DIR}/values.yaml"
WEIGHTS_FILE = f"{TRICK_OR_TREAT_DATA_DIR}/weights.yaml"
CONTENT_FILE = f"{TRICK_OR_TREAT_DATA_DIR}/content.json"

try:
    with open(VALUES_FILE) as f:
        _values = yaml.safe_load(f)
except FileNotFoundError as e:
    raise FileNotFoundError(
        f"Trick-or-treat values file not found: {e.filename}. "
        f"Expected file at: {VALUES_FILE}"
    ) from e
except yaml.YAMLError as e:
    raise ValueError(f"Invalid YAML syntax in trick-or-treat values file: {e}") from e
except Exception as e:
    raise RuntimeError(f"Unexpected error loading trick-or-treat values: {e}") from e


def _validate_values(values: dict) -> None:
    """Validate trick-or-treat game values.

    Args:
        values: Dictionary containing game configuration values.

    Raises:
        ValueError: If validation fails.
        KeyError: If required fields are missing.
    """
    required_sections = ["ingot_ranges", "jackpot_value", "backrooms", "quiz_master"]
    missing_sections = [s for s in required_sections if s not in values]
    if missing_sections:
        raise KeyError(f"Missing required sections in values file: {missing_sections}")

    ranges = values["ingot_ranges"]
    required_range_fields = ["low_min", "low_max", "high_min", "high_max"]
    missing_range_fields = [f for f in required_range_fields if f not in ranges]
    if missing_range_fields:
        raise KeyError(f"Missing required ingot_ranges fields: {missing_range_fields}")

    for field, value in ranges.items():
        if not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"ingot_ranges.{field} must be a positive integer, got: {value}"
            )

    if ranges["low_min"] >= ranges["low_max"]:
        raise ValueError(
            f"low_min ({ranges['low_min']}) must be < low_max ({ranges['low_max']})"
        )
    if ranges["high_min"] >= ranges["high_max"]:
        raise ValueError(
            f"high_min ({ranges['high_min']}) must be < high_max ({ranges['high_max']})"
        )

    if not isinstance(values["jackpot_value"], int) or values["jackpot_value"] <= 0:
        raise ValueError(
            f"jackpot_value must be a positive integer, got: {values['jackpot_value']}"
        )

    backrooms = values["backrooms"]
    required_backrooms_fields = [
        "door_count",
        "treasure_min",
        "treasure_max",
        "monster_min",
        "monster_max",
    ]
    missing_backrooms = [f for f in required_backrooms_fields if f not in backrooms]
    if missing_backrooms:
        raise KeyError(f"Missing required backrooms fields: {missing_backrooms}")

    for field, value in backrooms.items():
        if not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"backrooms.{field} must be a positive integer, got: {value}"
            )

    if backrooms["treasure_min"] >= backrooms["treasure_max"]:
        raise ValueError(
            f"backrooms.treasure_min ({backrooms['treasure_min']}) must be < "
            f"treasure_max ({backrooms['treasure_max']})"
        )
    if backrooms["monster_min"] >= backrooms["monster_max"]:
        raise ValueError(
            f"backrooms.monster_min ({backrooms['monster_min']}) must be < "
            f"monster_max ({backrooms['monster_max']})"
        )

    quiz = values["quiz_master"]
    required_quiz_fields = [
        "correct_min",
        "correct_max",
        "wrong_penalty_min",
        "wrong_penalty_max",
        "penalty_chance",
    ]
    missing_quiz = [f for f in required_quiz_fields if f not in quiz]
    if missing_quiz:
        raise KeyError(f"Missing required quiz_master fields: {missing_quiz}")

    for field in [
        "correct_min",
        "correct_max",
        "wrong_penalty_min",
        "wrong_penalty_max",
    ]:
        value = quiz[field]
        if not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"quiz_master.{field} must be a positive integer, got: {value}"
            )

    penalty_chance = quiz["penalty_chance"]
    if not isinstance(penalty_chance, (int, float)):
        raise ValueError(
            f"quiz_master.penalty_chance must be a number, got: {penalty_chance}"
        )
    if not 0 <= penalty_chance <= 1:
        raise ValueError(
            f"quiz_master.penalty_chance must be between 0 and 1, got: {penalty_chance}"
        )

    if quiz["correct_min"] >= quiz["correct_max"]:
        raise ValueError(
            f"quiz_master.correct_min ({quiz['correct_min']}) must be < "
            f"correct_max ({quiz['correct_max']})"
        )
    if quiz["wrong_penalty_min"] >= quiz["wrong_penalty_max"]:
        raise ValueError(
            f"quiz_master.wrong_penalty_min ({quiz['wrong_penalty_min']}) must be < "
            f"wrong_penalty_max ({quiz['wrong_penalty_max']})"
        )


_validate_values(_values)

LOW_INGOT_MIN = _values["ingot_ranges"]["low_min"]
LOW_INGOT_MAX = _values["ingot_ranges"]["low_max"]
HIGH_INGOT_MIN = _values["ingot_ranges"]["high_min"]
HIGH_INGOT_MAX = _values["ingot_ranges"]["high_max"]
JACKPOT_VALUE = _values["jackpot_value"]

# Backrooms configuration
BACKROOMS_DOOR_COUNT = _values["backrooms"]["door_count"]
BACKROOMS_TREASURE_MIN = _values["backrooms"]["treasure_min"]
BACKROOMS_TREASURE_MAX = _values["backrooms"]["treasure_max"]
BACKROOMS_MONSTER_MIN = _values["backrooms"]["monster_min"]
BACKROOMS_MONSTER_MAX = _values["backrooms"]["monster_max"]

# Quiz Master configuration
QUIZ_CORRECT_MIN = _values["quiz_master"]["correct_min"]
QUIZ_CORRECT_MAX = _values["quiz_master"]["correct_max"]
QUIZ_WRONG_PENALTY_MIN = _values["quiz_master"]["wrong_penalty_min"]
QUIZ_WRONG_PENALTY_MAX = _values["quiz_master"]["wrong_penalty_max"]
QUIZ_PENALTY_CHANCE = _values["quiz_master"]["penalty_chance"]


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
    with open(WEIGHTS_FILE) as f:
        _weights = yaml.safe_load(f)
except FileNotFoundError as e:
    raise FileNotFoundError(
        f"Trick-or-treat weights file not found: {e.filename}. "
        f"Expected file at: {WEIGHTS_FILE}"
    ) from e
except yaml.YAMLError as e:
    raise ValueError(f"Invalid YAML syntax in trick-or-treat weights file: {e}") from e
except Exception as e:
    raise RuntimeError(f"Unexpected error loading trick-or-treat weights: {e}") from e

_validate_weights(_weights)


class TrickOrTreat(Enum):
    """Trick-or-treat outcome types with probability weights loaded from YAML."""

    JACKPOT_INGOTS = _weights["JACKPOT_INGOTS"]
    REMOVE_ALL_INGOTS_TRICK = _weights["REMOVE_ALL_INGOTS_TRICK"]
    DOUBLE_OR_NOTHING = _weights["DOUBLE_OR_NOTHING"]
    STEAL = _weights["STEAL"]
    QUIZ_MASTER = _weights["QUIZ_MASTER"]
    BACKROOMS = _weights["BACKROOMS"]
    REMOVE_INGOTS_HIGH = _weights["REMOVE_INGOTS_HIGH"]
    ADD_INGOTS_HIGH = _weights["ADD_INGOTS_HIGH"]
    REMOVE_INGOTS_LOW = _weights["REMOVE_INGOTS_LOW"]
    ADD_INGOTS_LOW = _weights["ADD_INGOTS_LOW"]
    JOKE = _weights["JOKE"]
    GIF = _weights["GIF"]
