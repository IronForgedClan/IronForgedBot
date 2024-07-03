import json
import logging
from typing import List, Type, TypedDict, TypeVar, cast, NotRequired

T = TypeVar("T", bound=TypedDict)


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
    _dataPath = "data/"

    try:
        with open(f"{_dataPath}{file_name}", "r") as file:
            logging.debug(f"Reading file: {file.name}")
            data = json.load(file)

            if not isinstance(data, list):
                raise TypeError(f"{file_name} does not contain an array/list")

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

            return cast(List[T], data)

    except (TypeError, KeyError, FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(e)
        return None


BOSSES = load_json_data("bosses.json", Activity)
CLUES = load_json_data("clues.json", Activity)
RAIDS = load_json_data("raids.json", Activity)
SKILLS = load_json_data("skills.json", Skill)
