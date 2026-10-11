from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NotRequired, TypedDict

QUIZ_OPTION_COUNT = 4
ContentMessage = str | list[str]


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
    no_ingots_message: ContentMessage


class JackpotData(TypedDict):
    """Jackpot outcome messages."""

    success_prefix: ContentMessage
    claimed_message: ContentMessage


class TrickData(TypedDict):
    """Remove-all-ingots trick outcome message."""

    message: ContentMessage


class DoubleOrNothingData(TypedDict):
    """Double-or-nothing outcome messages."""

    offer: ContentMessage
    win: ContentMessage
    lose: ContentMessage
    keep: ContentMessage
    expired: ContentMessage


class StealData(TypedDict):
    """Steal outcome messages."""

    offer: ContentMessage
    success: ContentMessage
    failure: ContentMessage
    walk_away: ContentMessage
    expired: ContentMessage
    no_targets: ContentMessage
    target_no_ingots: ContentMessage
    user_no_ingots: ContentMessage


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
    room_outcome_weights: dict[str, dict[str, float]]
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

    intro: ContentMessage
    questions: list[QuizQuestion]
    correct_message: ContentMessage
    wrong_lucky_message: ContentMessage
    wrong_penalty_message: ContentMessage
    expired_message: ContentMessage


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
    content_messages: dict[str, deque[int]]


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
