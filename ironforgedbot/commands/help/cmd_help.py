import logging
import textwrap

import discord
from tabulate import tabulate

from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.helpers import build_discord_link, find_emoji
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_code_block
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators.require_role import require_role
from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)

_STATS_LOOKUP: set[str] = {"score", "breakdown", "check", "ingots"}
_GAMES_FUN: set[str] = {"raffle", "reset_rng", "eight_ball", "spin", "trick_or_treat"}


def _get_ingot_cost(cmd: discord.app_commands.Command) -> int | None:
    """Walk the decorator chain to find a stamped ingot_cost attribute."""
    fn = cmd.callback
    while fn is not None:
        cost = getattr(fn, "ingot_cost", None)
        if cost is not None:
            return cost
        fn = getattr(fn, "__wrapped__", None)
    return None


_DESC_WRAP_WIDTH = 35


def _build_ascii_table(cmds: list[discord.app_commands.Command]) -> str:
    """Build a tabulate simple-format ASCII table of commands wrapped in a code block."""
    rows = []
    for cmd in cmds:
        desc = cmd.description or ""
        if desc and desc[0] in ("🔒", "💰"):
            desc = desc[2:].lstrip()

        cost = _get_ingot_cost(cmd)
        if cost is not None:
            desc = f"{desc} ({cost:,} ingots)"

        wrapped = "\n".join(textwrap.wrap(desc, _DESC_WRAP_WIDTH))
        rows.append([f"{cmd.name}", wrapped])

    return text_code_block(
        tabulate(rows, headers=["Command", "Description"], tablefmt="simple")
    )


def _build_commands_description() -> str:
    rules = f"<#{CONFIG.RULES_CHANNEL_ID}>"
    shop = f"<#{CONFIG.INGOT_SHOP_CHANNEL_ID}>"
    return (
        f"Look up scores, check your rank, and view player stats. "
        f"Activity requirements are in {rules}, ingot info is in {shop}."
    )


def _build_activities_description(has_trick_or_treat: bool) -> str:
    desc = "Spend your ingots and have a bit of fun with the clan."
    if has_trick_or_treat and getattr(CONFIG, "TRICK_OR_TREAT_CHANNEL_ID", None):
        tot = f"<#{CONFIG.TRICK_OR_TREAT_CHANNEL_ID}>"
        desc += f"\n\n-# **NEW:** Head over to {tot} and try your luck!"
    if STATE.state["raffle_on"]:
        raffle = f"<#{CONFIG.RAFFLE_CHANNEL_ID}>"
        desc += (
            f"\n\n-# **NEW:** There is a raffle happening __right now__ in {raffle}!"
        )
    return desc


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
async def cmd_help(interaction: discord.Interaction):
    """Display all active bot commands with descriptions."""
    tree = interaction.client.tree
    all_commands = tree.get_commands()

    stats_cmds: list[discord.app_commands.Command] = []
    games_cmds: list[discord.app_commands.Command] = []
    other_cmds: list[discord.app_commands.Command] = []

    for cmd in all_commands:
        if cmd.name == "help":
            continue
        desc = cmd.description or ""
        if desc.startswith("🔒"):
            continue
        if cmd.name == "raffle" and not STATE.state["raffle_on"]:
            continue
        if cmd.name in _STATS_LOOKUP:
            stats_cmds.append(cmd)
        elif cmd.name in _GAMES_FUN:
            games_cmds.append(cmd)
        else:
            other_cmds.append(cmd)

    dwh_emoji = find_emoji("DWH")
    embed = build_response_embed(
        title=f"{dwh_emoji} Iron Forged Commands",
        description=(
            f"Everything you need to keep up with the clan, right here in Discord. "
            f"Check your score and rank, see where your ingots stand, and explore ways to earn and spend them. "
            f"Use `/` in <#{CONFIG.BOT_COMMANDS_CHANNEL_ID}> to browse available commands. "
            f"Feedback and suggestions are always welcome - drop them in <#{CONFIG.CREATE_TICKET_CHANNEL_ID}>."
        ),
        color=discord.Colour.blue(),
    )

    sections = []
    if stats_cmds:
        sections.append(("Core Commands", _build_commands_description(), stats_cmds))

    has_trick_or_treat = any(c.name == "trick_or_treat" for c in games_cmds)
    if games_cmds:
        sections.append(
            (
                "Activities",
                _build_activities_description(has_trick_or_treat),
                games_cmds,
            )
        )

    if other_cmds:
        sections.append(
            (
                "Miscellaneous",
                "Handy utilities that don't fit anywhere else.",
                other_cmds,
            )
        )

    for title, description, cmds in sections:
        embed.add_field(
            name=f"{EMPTY_SPACE}\n{title}",
            value=f"{description}\n\n{_build_ascii_table(cmds)}",
            inline=False,
        )

    changelog_link = build_discord_link(CONFIG.BOT_CHANGELOG_CHANNEL_ID)
    embed.add_field(
        name=EMPTY_SPACE,
        value=f"-# _ironforgedbot⠀•⠀v{CONFIG.BOT_VERSION}⠀•⠀[changelog]({changelog_link})_",
        inline=False,
    )

    await interaction.followup.send(embed=embed)
