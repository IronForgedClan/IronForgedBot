from typing import Any, Dict, List, Tuple, TypedDict, Union

from apscheduler.executors.base import logging
import requests

from ironforgedbot.commands.hiscore.constants import Skill, SKILLS, ACTIVITIES
from ironforgedbot.commands.hiscore.points import (
    SKILL_POINTS_REGULAR,
    SKILL_POINTS_PAST_99,
    ACTIVITY_POINTS,
)
from ironforgedbot.common.helpers import normalize_discord_string

HISCORES_PLAYER_URL = (
    "https://secure.runescape.com/m=hiscore_oldschool/index_lite.json?player={player}"
)
LEVEL_99_EXPERIENCE = 13034431


class ActivityInfo(TypedDict):
    kc: int
    points: int


def score_info(player_name: str) -> Tuple[List[Skill], Any]:
    player_name = normalize_discord_string(player_name)
    data = _fetch_data(player_name)

    skills_info = _get_skills_info(data)
    activities_info = _get_activities_info(data)

    return skills_info, activities_info


def points_total(player_name: str) -> int:
    player_name = normalize_discord_string(player_name)

    skills, activities = score_info(player_name)
    points = 0

    for skill in skills:
        points += skill["points"]

    for _, activity in activities.items():
        points += activity["points"]

    return points


def _fetch_data(player_name: str):
    try:
        resp = requests.get(HISCORES_PLAYER_URL.format(player=player_name), timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Looking up {player_name} on hiscores failed. Got status code {resp.status_code}"
            )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Encountered an error calling Runescape API: {e}")

    return resp.json()


def _get_skills_info(score_data) -> List[Skill]:
    output = []

    for skill_data in score_data["skills"]:
        skill_name = skill_data["name"]

        if skill_name.lower() == "overall":
            continue

        skill = SKILLS.get_skill_by_long_name(skill_name)

        if skill is None:
            logging.info(f"Skill name '{skill_name}' not found")
            continue

        if (
            skill_name not in SKILL_POINTS_REGULAR
            or skill_name not in SKILL_POINTS_PAST_99
        ):
            logging.info(f"No points defined for skill '{skill_name}'")
            continue

        skill_level = int(skill_data["level"]) if int(skill_data["level"]) > 1 else 1
        experience = int(skill_data["xp"]) if int(skill_data["xp"]) > 0 else 0

        if skill_level < 99:
            points = int(experience / SKILL_POINTS_REGULAR[skill_name])
        else:
            points = int(LEVEL_99_EXPERIENCE / SKILL_POINTS_REGULAR[skill_name]) + int(
                (experience - LEVEL_99_EXPERIENCE) / SKILL_POINTS_PAST_99[skill_name]
            )

        output.append(
            {
                **skill,
                **{
                    "xp": experience,
                    "level": skill_level,
                    "points": points,
                },
            }
        )

    return output


def _get_activities_info(score_data) -> Dict[str, ActivityInfo]:
    activities = {}

    for activity in score_data["activities"]:
        if not ACTIVITIES.has_value(activity["name"]):
            continue

        kc = int(activity["score"])
        if kc < 1:
            continue

        activity_constant = ACTIVITIES(activity["name"])
        if activity_constant not in ACTIVITY_POINTS:
            continue

        points = int(kc / ACTIVITY_POINTS[activity_constant])
        if 0 == points:
            continue

        activities[activity_constant] = {"kc": kc, "points": points}

    return activities
