from datetime import datetime
from typing import Any

from pydantic import BaseModel

from ironforgedbot.models.score import ActivityScore, ScoreBreakdown, SkillScore


class SkillScoreSchema(BaseModel):
    name: str
    display_name: str | None = None
    display_order: int
    emoji_key: str
    level: int
    xp: int
    points: int

    @classmethod
    def from_skill(cls, s: SkillScore) -> "SkillScoreSchema":
        return cls(
            name=s.name,
            display_name=s.display_name,
            display_order=s.display_order,
            emoji_key=s.emoji_key,
            level=s.level,
            xp=s.xp,
            points=s.points,
        )


class ActivityScoreSchema(BaseModel):
    name: str
    display_name: str | None = None
    display_order: int
    emoji_key: str
    kc: int
    points: int

    @classmethod
    def from_activity(cls, a: ActivityScore) -> "ActivityScoreSchema":
        return cls(
            name=a.name,
            display_name=a.display_name,
            display_order=a.display_order,
            emoji_key=a.emoji_key,
            kc=a.kc,
            points=a.points,
        )


class PlayerScoreResponse(BaseModel):
    player_name: str
    skills: list[SkillScoreSchema]
    clues: list[ActivityScoreSchema]
    raids: list[ActivityScoreSchema]
    bosses: list[ActivityScoreSchema]
    total_points: int

    @classmethod
    def from_breakdown(
        cls, player_name: str, breakdown: ScoreBreakdown
    ) -> "PlayerScoreResponse":
        points = sum(s.points for s in breakdown.skills)
        points += sum(
            a.points for a in (breakdown.clues + breakdown.raids + breakdown.bosses)
        )
        return cls(
            player_name=player_name,
            skills=[SkillScoreSchema.from_skill(s) for s in breakdown.skills],
            clues=[ActivityScoreSchema.from_activity(a) for a in breakdown.clues],
            raids=[ActivityScoreSchema.from_activity(a) for a in breakdown.raids],
            bosses=[ActivityScoreSchema.from_activity(a) for a in breakdown.bosses],
            total_points=points,
        )


class ScoreHistoryEntry(BaseModel):
    period_days: int
    score: int | None
    snapshot_date: datetime | None = None


class ScoreHistoryResponse(BaseModel):
    discord_id: int
    entries: list[ScoreHistoryEntry]

    @classmethod
    def from_periods(
        cls, discord_id: int, periods: dict[int, int | None]
    ) -> "ScoreHistoryResponse":
        return cls(
            discord_id=discord_id,
            entries=[
                ScoreHistoryEntry(period_days=p, score=s) for p, s in periods.items()
            ],
        )
