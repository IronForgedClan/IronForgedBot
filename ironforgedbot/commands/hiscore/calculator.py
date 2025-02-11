import logging
from typing import List, NotRequired, Tuple, TypedDict

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.ranks import RANK, get_rank_from_points
from ironforgedbot.http import HTTP
from ironforgedbot.storage.data import BOSSES, CLUES, RAIDS, SKILLS

logger = logging.getLogger(__name__)

HISCORES_PLAYER_URL = (
    "https://secure.runescape.com/m=hiscore_oldschool/index_lite.json?player={player}"
)
LEVEL_99_EXPERIENCE = 13034431


class HiscoresError(Exception):
    def __init__(
        self,
        message="Error response from the hiscores, please wait a moment and try again.",
    ):
        self.message = message
        super().__init__(self.message)


class HiscoresNotFound(Exception):
    def __init__(self, message="Player not found on the hiscores."):
        self.message = message
        super().__init__(self.message)


class ActivityScore(TypedDict):
    name: str
    display_name: NotRequired[str]
    display_order: int
    emoji_key: str
    kc: int
    points: int


class SkillScore(TypedDict):
    name: str
    display_name: NotRequired[str]
    display_order: int
    emoji_key: str
    xp: int
    level: int
    points: int


class ScoreBreakdown:
    def __init__(
        self,
        skills: List[SkillScore],
        clues: List[ActivityScore],
        raids: List[ActivityScore],
        bosses: List[ActivityScore],
    ):
        self.skills = skills
        self.clues = clues
        self.raids = raids
        self.bosses = bosses


async def score_info(
    player_name: str,
) -> ScoreBreakdown:
    player_name = normalize_discord_string(player_name)
    data = await HTTP.get(HISCORES_PLAYER_URL.format(player=player_name))

    if data["status"] == 404:
        raise HiscoresNotFound()

    if data["status"] != 200:
        logger.error(data["body"])
        raise HiscoresError()

    skills = _get_skills_info(data["body"])
    clues, raids, bosses = _get_activities_info(data["body"])

    return ScoreBreakdown(skills, clues, raids, bosses)


async def get_player_points_total(player_name: str) -> int:
    player_name = normalize_discord_string(player_name)
    data = await score_info(player_name)

    activities = data.clues + data.raids + data.bosses

    points = 0
    for skill in data.skills:
        points += skill["points"]

    for activity in activities:
        points += activity["points"]

    return points


async def get_rank(player_name: str) -> RANK:
    try:
        total_points = await get_player_points_total(player_name)
    except RuntimeError as e:
        raise e

    return RANK(get_rank_from_points(total_points))


def _get_skills_info(score_data) -> List[SkillScore]:
    if SKILLS is None or score_data is None or score_data["skills"] is None:
        raise RuntimeError("Unable to read skills data")

    output = []

    for skill_data in score_data["skills"]:
        skill_name = skill_data["name"]

        if skill_name.lower() == "overall":
            continue

        skill = next((skill for skill in SKILLS if skill["name"] == skill_name), None)

        if skill is None:
            logger.info(f"Skill name '{skill_name}' not found")
            continue

        skill_level = int(skill_data["level"]) if int(skill_data["level"]) > 1 else 1
        experience = int(skill_data["xp"]) if int(skill_data["xp"]) > 0 else 0

        if skill_level < 99:
            points = int(experience / skill["xp_per_point"])
        else:
            points = int(LEVEL_99_EXPERIENCE / skill["xp_per_point"]) + int(
                (experience - LEVEL_99_EXPERIENCE) / skill["xp_per_point_post_99"]
            )

        data: SkillScore = {
            "name": skill["name"],
            "display_order": skill["display_order"],
            "emoji_key": skill["emoji_key"],
            "level": skill_level,
            "xp": experience,
            "points": points,
        }
        output.append(data)

    return output


def _get_activities_info(
    score_data,
) -> Tuple[List[ActivityScore], List[ActivityScore], List[ActivityScore]]:
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
            data: ActivityScore = {
                "name": clue["name"],
                "display_order": clue["display_order"],
                "emoji_key": clue["emoji_key"],
                "kc": kc,
                "points": max(int(kc / clue["kc_per_point"]), 0),
            }

            if clue.get("display_name", None) is not None:
                data["display_name"] = clue.get("display_name", "")

            clues.append(data)
            continue

        raid = next((raid for raid in RAIDS if raid["name"] == activity_name), None)
        if raid is not None:
            kc = max(int(activity["score"]), 0)
            data: ActivityScore = {
                "name": raid["name"],
                "display_order": raid["display_order"],
                "emoji_key": raid["emoji_key"],
                "kc": kc,
                "points": max(int(kc / raid["kc_per_point"]), 0),
            }

            if raid.get("display_name", None) is not None:
                data["display_name"] = raid.get("display_name", "")

            raids.append(data)
            continue

        boss = next((boss for boss in BOSSES if boss["name"] == activity_name), None)
        if boss is not None:
            kc = max(int(activity["score"]), 0)

            if kc < 1:
                continue

            data: ActivityScore = {
                "name": boss["name"],
                "display_order": boss["display_order"],
                "emoji_key": boss["emoji_key"],
                "kc": kc,
                "points": max(int(kc / boss["kc_per_point"]), 0),
            }

            if boss.get("display_name", None) is not None:
                data["display_name"] = boss.get("display_name", "")

            bosses.append(data)
            continue

        logger.debug(f"Activity '{activity_name}' not handled")

    return clues, raids, bosses
