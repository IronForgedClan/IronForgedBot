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

    POSITIVE_MESSAGES: list[str]
    NEGATIVE_MESSAGES: list[str]
    NO_INGOTS_MESSAGE: str


class JackpotData(TypedDict):
    """Jackpot outcome messages."""

    SUCCESS_PREFIX: str
    CLAIMED_MESSAGE: str


class TrickData(TypedDict):
    """Remove-all-ingots trick outcome message."""

    MESSAGE: str


class DoubleOrNothingData(TypedDict):
    """Double-or-nothing outcome messages."""

    OFFER: str
    WIN: str
    LOSE: str
    KEEP: str
    EXPIRED: str


class StealData(TypedDict):
    """Steal outcome messages."""

    OFFER: str
    SUCCESS: str
    FAILURE: str
    WALK_AWAY: str
    EXPIRED: str
    NO_TARGETS: str
    TARGET_NO_INGOTS: str
    USER_NO_INGOTS: str


class BackroomsData(TypedDict):
    """Backrooms outcome messages and content."""

    INTRO: str
    DOOR_LABELS: list[str]
    TREASURE_MESSAGES: list[str]
    MONSTER_MESSAGES: list[str]
    ESCAPE_MESSAGES: list[str]
    LUCKY_ESCAPE_MESSAGES: list[str]
    OPENING_DOOR: str
    EXPIRED: str
    THUMBNAILS: list[str]


class JokeData(TypedDict):
    """Joke outcome messages."""

    MESSAGES: list[str]


class QuizData(TypedDict):
    """Quiz master outcome messages and questions."""

    INTRO: str
    QUESTIONS: list[QuizQuestion]
    CORRECT_MESSAGE: str
    WRONG_LUCKY_MESSAGE: str
    WRONG_PENALTY_MESSAGE: str
    EXPIRED_MESSAGE: str
