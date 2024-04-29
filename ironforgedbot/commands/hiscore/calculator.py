from typing import Dict, TypedDict

import requests

from ironforgedbot.commands.hiscore.constants import SKILLS, ACTIVITIES
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


class SkillInfo(TypedDict):
    xp: int
    level: int
    points: int


class ActivityInfo(TypedDict):
    kc: int
    points: int


def score_info(player_name: str):
    player_name = normalize_discord_string(player_name)

    data = _fetch_data(player_name)
    skills_info = _get_skills_info(data)
    activities_info = _get_activities_info(data)
    return skills_info, activities_info


def points_total(player_name: str) -> int:
    player_name = normalize_discord_string(player_name)

    skills, activities = score_info(player_name)
    points = 0

    for _, skill in skills.items():
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


def _get_skills_info(score_data) -> Dict[str, SkillInfo]:
    skills = {}

    for skill in score_data["skills"]:
        if not SKILLS.has_value(skill["name"]):
            continue

        skill_constant = SKILLS(skill["name"])

        if (
            skill_constant not in SKILL_POINTS_REGULAR
            or skill_constant not in SKILL_POINTS_PAST_99
        ):
            continue

        skill_level = int(skill["level"]) if int(skill["level"]) > 1 else 1
        experience = int(skill["xp"]) if int(skill["xp"]) > 0 else 0

        if skill_level < 99:
            points = int(experience / SKILL_POINTS_REGULAR[skill_constant])
        else:
            points = int(
                LEVEL_99_EXPERIENCE / SKILL_POINTS_REGULAR[skill_constant]
            ) + int(
                (experience - LEVEL_99_EXPERIENCE)
                / SKILL_POINTS_PAST_99[skill_constant]
            )

        skills[skill_constant] = {
            "xp": experience,
            "level": skill_level,
            "points": points,
        }

    return skills


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
