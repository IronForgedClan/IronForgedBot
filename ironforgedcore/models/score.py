from dataclasses import dataclass
from typing import Optional


@dataclass
class ActivityScore:
    name: str
    display_name: Optional[str]
    display_order: int
    emoji_key: str
    kc: int
    points: int


@dataclass
class SkillScore:
    name: str
    display_name: Optional[str]
    display_order: int
    emoji_key: str
    xp: int
    level: int
    points: int


@dataclass
class ScoreBreakdown:
    skills: list[SkillScore]
    clues: list[ActivityScore]
    raids: list[ActivityScore]
    bosses: list[ActivityScore]
