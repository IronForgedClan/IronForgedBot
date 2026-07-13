import json
import os


def get_api_version() -> str:
    version_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "versions.json"
    )
    with open(version_file, "r") as file:
        return json.load(file)["api"]
