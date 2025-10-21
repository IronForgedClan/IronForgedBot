from collections import deque
from typing import TypedDict


class QuizOption(TypedDict):
    """A single quiz answer option."""

    text: str
    emoji: str


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


class BackroomsData(TypedDict):
    """Backrooms outcome messages and content."""

    intro: str
    door_labels: list[str]
    treasure_messages: list[str]
    monster_messages: list[str]
    escape_messages: list[str]
    lucky_escape_messages: list[str]
    opening_door: str
    expired: str
    thumbnails: list[str]


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
    positive_message: deque[int]
    negative_message: deque[int]
    quiz_question: deque[int]
    joke: deque[int]
