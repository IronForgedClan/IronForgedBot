from typing import List, Tuple

import requests
from apscheduler.executors.base import logging

from ironforgedbot.commands.hiscore.constants import (
    ACTIVITIES,
    BOSSES,
    CLUES,
    IGNORED_ACTIVITIES,
    RAIDS,
    SKILLS,
    Activity,
    Skill,
)
from ironforgedbot.commands.hiscore.points import (
    ACTIVITY_POINTS,
    SKILL_POINTS_PAST_99,
    SKILL_POINTS_REGULAR,
)
from ironforgedbot.common.helpers import normalize_discord_string

HISCORES_PLAYER_URL = (
    "https://secure.runescape.com/m=hiscore_oldschool/index_lite.json?player={player}"
)
LEVEL_99_EXPERIENCE = 13034431


class ScoreBreakdown:
    def __init__(
        self,
        skills: List[Skill],
        clues: List[Activity],
        raids: List[Activity],
        bosses: List[Activity],
    ):
        self.skills = skills
        self.clues = clues
        self.raids = raids
        self.bosses = bosses


def score_info(
    player_name: str,
) -> ScoreBreakdown:
    player_name = normalize_discord_string(player_name)
    data = _fetch_data(player_name)

    skills = _get_skills_info(data)
    clues, raids, bosses = _get_activities_info(data)

    return ScoreBreakdown(skills, clues, raids, bosses)


def points_total(player_name: str) -> int:
    player_name = normalize_discord_string(player_name)

    data = score_info(player_name)
    activities = data.clues + data.raids + data.bosses

    points = 0

    for skill in data.skills:
        points += skill["points"]

    for activity in activities:
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

        skill = SKILLS.get_item_by_name(skill_name)

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


def _get_activities_info(
    score_data,
) -> Tuple[List[Activity], List[Activity], List[Activity]]:
    clues = []
    raids = []
    bosses = []

    for activity in score_data["activities"]:
        activity_name = activity["name"]

        if activity_name in IGNORED_ACTIVITIES.values():
            continue

        if not ACTIVITIES.has_item_name(activity_name):
            logging.warn(f"Activity '{activity_name}' not known")
            continue

        kc = max(int(activity["score"]), 0)
        points = max(int(kc / ACTIVITY_POINTS[activity_name]), 0)

        data = {"kc": kc, "points": points}

        clue = CLUES.get_item_by_name(activity_name)
        if clue is not None:
            clues.append({**clue, **data})
            continue

        raid = RAIDS.get_item_by_name(activity_name)
        if raid is not None:
            raids.append({**raid, **data})
            continue

        boss = BOSSES.get_item_by_name(activity_name)
        if boss is not None:
            if kc < 1:
                continue

            bosses.append({**boss, **data})
            continue

        logging.error(f"Activity '{activity_name}' processed but not sorted")

    return clues, raids, bosses
