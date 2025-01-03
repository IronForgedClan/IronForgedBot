import io
import json

import discord

from ironforgedbot.state import STATE


def get_internal_state() -> discord.File:
    """Returns internal state dict as discord.File object"""
    json_bytes = io.BytesIO(json.dumps(STATE.state, indent=2).encode("utf-8"))
    json_bytes.seek(0)

    return discord.File(json_bytes, "state.json")
