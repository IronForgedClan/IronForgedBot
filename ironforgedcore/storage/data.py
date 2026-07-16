import json
import logging
import sys
from typing import List, NotRequired, Type, TypedDict, TypeVar, cast

T = TypeVar("T", bound=TypedDict)
logger = logging.getLogger(__name__)


class Skill(TypedDict):
    name: str
    display_order: int
    emoji_key: str
    xp_per_point: int
    xp_per_point_post_99: int


class Activity(TypedDict):
    name: str
    display_name: NotRequired[str]
    display_order: int
    emoji_key: str
    kc_per_point: int


def load_json_data(file_name: str, type: Type[T]) -> List[T] | None:
    with open(f"{file_name}", "r") as file:
        logger.debug(f"Reading file: {file_name}")
        data = json.load(file)

        if not isinstance(data, list):
            raise TypeError(f"{file_name}: does not contain an array/list")

        for item in data:
            if not isinstance(item, dict):
                raise TypeError(f"{file_name}: does not contain object/dict")

            for key in type.__annotations__.keys():
                if key not in item and key in type.__optional_keys__:
                    item[key] = None
                elif key not in item:
                    raise KeyError(
                        f"{file_name}: object missing key ({key}) for type ({type.__name__})"
                    )

        output = cast(List[T], data)
        if output is None or len(output) < 1:
            raise ValueError(f"{file_name}: output result is invalid")

        return output


try:
    BOSSES = load_json_data("data/bosses.json", Activity)
    CLUES = load_json_data("data/clues.json", Activity)
    RAIDS = load_json_data("data/raids.json", Activity)
    SKILLS = load_json_data("data/skills.json", Skill)
    logger.info("Loaded local data successfully")
except Exception as e:
    logger.critical(e)
    sys.exit(1)
