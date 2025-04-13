import logging
from dataclasses import dataclass
from typing import Optional

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.ranks import RANK, get_rank_from_points
from ironforgedbot.http import AsyncHttpClient
from ironforgedbot.storage.data import BOSSES, CLUES, RAIDS, SKILLS

logger = logging.getLogger(__name__)


class HiscoresError(Exception):
    def __init__(
        self,
        message="Error response from the hiscores",
    ):
        self.message = message
        super().__init__(self.message)


class HiscoresNotFound(Exception):
    def __init__(
        self,
        message="Player not found on the hiscores",
    ):
        self.message = message
        super().__init__(self.message)


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


class ScoreBreakdown:
    def __init__(
        self,
        skills: list[SkillScore],
        clues: list[ActivityScore],
        raids: list[ActivityScore],
        bosses: list[ActivityScore],
    ):
        self.skills = skills
        self.clues = clues
        self.raids = raids
        self.bosses = bosses


class ScoreService:
    def __init__(self, http: AsyncHttpClient):
        self.http = http
        self.hiscores_url = (
            "https://secure.runescape.com/m=hiscore_oldschool/"
            "index_lite.json?player={rsn}"
        )
        self.level_99_xp = 13_034_431

    async def get_player_score(
        self,
        player_name: str,
    ) -> ScoreBreakdown:
        player_name = normalize_discord_string(player_name)
        data = await self.http.get(self.hiscores_url.format(rsn=player_name))

        logger.info("using new score service")
        if data["status"] == 404:
            raise HiscoresNotFound()

        if data["status"] != 200:
            logger.error(data["body"])
            raise HiscoresError(message=f"Unexpected response code {data['status']}")

        skills = self._get_skills_info(data["body"])
        clues, raids, bosses = self._get_activities_info(data["body"])

        return ScoreBreakdown(skills, clues, raids, bosses)

    def _get_skills_info(self, score_data) -> list[SkillScore]:
        if SKILLS is None or score_data is None or score_data["skills"] is None:
            raise RuntimeError("Unable to read skills data")

        output = []

        for skill_data in score_data["skills"]:
            skill_name = skill_data["name"]

            if skill_name.lower() == "overall":
                continue

            skill = next(
                (skill for skill in SKILLS if skill["name"] == skill_name), None
            )

            if skill is None:
                logger.info(f"Skill name '{skill_name}' not found")
                continue

            skill_level = (
                int(skill_data["level"]) if int(skill_data["level"]) > 1 else 1
            )
            experience = int(skill_data["xp"]) if int(skill_data["xp"]) > 0 else 0

            if skill_level < 99:
                points = int(experience / skill["xp_per_point"])
            else:
                points = int(self.level_99_xp / skill["xp_per_point"]) + int(
                    (experience - self.level_99_xp) / skill["xp_per_point_post_99"]
                )

            data: SkillScore = SkillScore(
                name=skill["name"],
                display_name=None,
                display_order=skill["display_order"],
                emoji_key=skill["emoji_key"],
                level=skill_level,
                xp=experience,
                points=points,
            )

            output.append(data)

        return output

    def _get_activities_info(
        self,
        score_data,
    ) -> tuple[list[ActivityScore], list[ActivityScore], list[ActivityScore]]:
        if CLUES is None or BOSSES is None or RAIDS is None:
            raise RuntimeError("Unable to read activity data")

        clues = []
        raids = []
        bosses = []

        for activity in score_data["activities"]:
            activity_name = activity["name"]

            clue = next((clue for clue in CLUES if clue["name"] == activity_name), None)
            if clue is not None:
                kc = max(int(activity["score"]), 0)
                data = ActivityScore(
                    name=clue["name"],
                    display_name=None,
                    display_order=clue["display_order"],
                    emoji_key=clue["emoji_key"],
                    kc=kc,
                    points=max(int(kc / clue["kc_per_point"]), 0),
                )

                if clue.get("display_name", None) is not None:
                    data.display_name = clue.get("display_name", "")

                clues.append(data)
                continue

            raid = next((raid for raid in RAIDS if raid["name"] == activity_name), None)
            if raid is not None:
                kc = max(int(activity["score"]), 0)

                data = ActivityScore(
                    name=raid["name"],
                    display_name=None,
                    display_order=raid["display_order"],
                    emoji_key=raid["emoji_key"],
                    kc=kc,
                    points=max(int(kc / raid["kc_per_point"]), 0),
                )

                if raid.get("display_name", None) is not None:
                    data.display_name = raid.get("display_name", "")

                raids.append(data)
                continue

            boss = next(
                (boss for boss in BOSSES if boss["name"] == activity_name), None
            )
            if boss is not None:
                kc = max(int(activity["score"]), 0)

                if kc < 1:
                    continue

                data = ActivityScore(
                    name=boss["name"],
                    display_name=None,
                    display_order=boss["display_order"],
                    emoji_key=boss["emoji_key"],
                    kc=kc,
                    points=max(int(kc / boss["kc_per_point"]), 0),
                )

                if boss.get("display_name", None) is not None:
                    data.display_name = boss.get("display_name", "")

                bosses.append(data)
                continue

            logger.debug(f"Activity '{activity_name}' not handled")

        return clues, raids, bosses

    async def get_player_points_total(self, player_name: str) -> int:
        player_name = normalize_discord_string(player_name)
        data = await self.get_player_score(player_name)

        activities = data.clues + data.raids + data.bosses

        points = 0
        for skill in data.skills:
            points += skill.points

        for activity in activities:
            points += activity.points

        return points

    async def get_rank(self, player_name: str) -> RANK:
        try:
            total_points = await self.get_player_points_total(player_name)
        except RuntimeError as e:
            raise e

        return RANK(get_rank_from_points(total_points))
