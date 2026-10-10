from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NotRequired, TypedDict

QUIZ_OPTION_COUNT = 4


class IngotAdjustmentFailure(StrEnum):
    NO_INGOTS = "no_ingots"
    ERROR = "error"


@dataclass(frozen=True)
class IngotAdjustment:
    new_total: int | None
    applied_quantity: int
    failure: IngotAdjustmentFailure | None = None


class QuizOption(TypedDict):
    """A single quiz answer option."""

    text: str
    emoji: NotRequired[str]


class QuizQuestion(TypedDict):
    """A quiz question with multiple choice answers."""

    question: str
    options: list[QuizOption]
    correct_index: int


class GeneralData(TypedDict):
    """General messages and responses used across outcomes."""

    positive_messages: list[str]
    negative_messages: list[str]
    no_ingots_message: str


class JackpotData(TypedDict):
    """Jackpot outcome messages."""

    success_prefix: str
    claimed_message: str


class TrickData(TypedDict):
    """Remove-all-ingots trick outcome message."""

    message: str


class DoubleOrNothingData(TypedDict):
    """Double-or-nothing outcome messages."""

    offer: str
    win: str
    lose: str
    keep: str
    expired: str


class StealData(TypedDict):
    """Steal outcome messages."""

    offer: str
    success: str
    failure: str
    walk_away: str
    expired: str
    no_targets: str
    target_no_ingots: str
    user_no_ingots: str


BackroomsMessageCategory = Literal[
    "intro",
    "continue_intro",
    "opening_door",
    "expired",
    "treasure",
    "fatal_monster",
    "monster",
    "escape",
    "bargain",
]


class BackroomsMessageHistory(TypedDict):
    """Recent-message indices for each Backrooms copy pool."""

    intro: deque[int]
    continue_intro: deque[int]
    opening_door: deque[int]
    expired: deque[int]
    treasure: deque[int]
    fatal_monster: deque[int]
    monster: deque[int]
    escape: deque[int]
    bargain: deque[int]


class BackroomsData(TypedDict):
    """Backrooms outcome messages and content."""

    intro_messages: list[str]
    continue_intro_messages: list[str]
    door_labels: list[str]
    treasure_messages: list[str]
    fatal_monster_messages: list[str]
    monster_messages: list[str]
    escape_messages: list[str]
    bargain_messages: list[str]
    opening_door_messages: list[str]
    expired_messages: list[str]
    thumbnails: list[str]
    suspense_thumbnail: str


class JokeData(TypedDict):
    """Joke outcome messages."""

    messages: list[str]


class QuizData(TypedDict):
    """Quiz master outcome messages and questions."""

    intro: str
    questions: list[QuizQuestion]
    correct_message: str
    wrong_lucky_message: str
    wrong_penalty_message: str
    expired_message: str


class HistoryDict(TypedDict):
    """History tracking for preventing recent repeats of content."""

    gif: deque[int]
    thumbnail: deque[int]
    backrooms_thumbnail: deque[int]
    backrooms_messages: BackroomsMessageHistory
    positive_message: deque[int]
    negative_message: deque[int]
    quiz_question: deque[int]
    joke: deque[int]


class MediaData(TypedDict):
    """Media URLs used by the event outcomes."""

    gifs: list[str]
    thumbnails: list[str]


class TrickOrTreatContent(TypedDict):
    """Validated top-level shape of trick-or-treat content JSON."""

    jackpot: JackpotData
    double_or_nothing: DoubleOrNothingData
    steal: StealData
    backrooms: BackroomsData
    quiz_master: QuizData
    joke: JokeData
    remove_all_trick: TrickData
    media: MediaData
    general: GeneralData
