import logging

import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators.require_role import require_role

logger = logging.getLogger(__name__)

_STATS_LOOKUP: set[str] = {"score", "breakdown", "check", "ingots", "whois"}
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


def _build_section_value(
    cmds: list[discord.app_commands.Command],
    description: str,
) -> str:
    """Build the full field value: description sentence + blank line + command list."""
    lines = [description, ""]
    ingot_emoji = find_emoji("Ingot")
    for cmd in cmds:
        desc = cmd.description or ""
        if desc and desc[0] in ("🔒", "💰"):
            desc = desc[2:].lstrip()

        cost = _get_ingot_cost(cmd)
        cost_str = f"{ingot_emoji} **{cost:,}** - " if cost is not None else ""
        lines.append(f"`/{cmd.name}` - {cost_str}_{desc}_")

    return "\n".join(lines)


def _build_stats_description() -> str:
    rules = f"<#{CONFIG.RULES_CHANNEL_ID}>"
    shop = f"<#{CONFIG.INGOT_SHOP_CHANNEL_ID}>"
    return (
        f"Track your progress and look up player information. "
        f"Activity requirements are listed in {rules}. "
        f"Spend your ingots in {shop}."
    )


def _build_games_description(has_trick_or_treat: bool) -> str:
    raffle = f"<#{CONFIG.RAFFLE_CHANNEL_ID}>"
    desc = f"Spend your ingots on a bit of fun. Head to {raffle} to try your luck with the raffle."
    if has_trick_or_treat and getattr(CONFIG, "TRICK_OR_TREAT_CHANNEL_ID", None):
        tot = f"<#{CONFIG.TRICK_OR_TREAT_CHANNEL_ID}>"
        desc += f" Try your luck with tricks or treats in {tot}."
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
        if cmd.name in _STATS_LOOKUP:
            stats_cmds.append(cmd)
        elif cmd.name in _GAMES_FUN:
            games_cmds.append(cmd)
        else:
            other_cmds.append(cmd)

    embed = build_response_embed(
        title=":robot: Bot Commands",
        description=f"Use any command by typing `/` in bot-commands.",
        color=discord.Colour.blue(),
    )

    if stats_cmds:
        embed.add_field(
            name="📊 Stats & Lookup",
            value=_build_section_value(stats_cmds, _build_stats_description()),
            inline=False,
        )

    has_trick_or_treat = any(c.name == "trick_or_treat" for c in games_cmds)
    if games_cmds:
        embed.add_field(
            name="🎲 Games & Fun",
            value=_build_section_value(
                games_cmds, _build_games_description(has_trick_or_treat)
            ),
            inline=False,
        )

    if other_cmds:
        embed.add_field(
            name="📌 Other",
            value=_build_section_value(other_cmds, "Additional commands."),
            inline=False,
        )

    await interaction.followup.send(embed=embed)
