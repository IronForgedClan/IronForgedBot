import logging

import discord
from discord import app_commands
from reactionmenu import ViewMenu, ViewButton

from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators import require_role
from ironforgedbot.config import CONFIG
from ironforgedbot.state import STATE
from ironforgedbot.common.responses import build_response_embed

logger = logging.getLogger(__name__)

IGNORED_COMMANDS = [
    "admin",
    "add_remove_ingots",
    "roster",
    "get_role_members",
]


@require_role(ROLE.MEMBER)
async def cmd_help(interaction: discord.Interaction):
    RAFFLE = STATE.state.get("raffle_on", False)
    tree = interaction.client.tree

    context = {
        "score": (
            "• **Optional**: `/score [player]:` to check another player's score.\n"
            "• If omitted, it will default to your nickname.\n"
            "• Score is based on skilling, bossing, raids, and clue completion."
        ),
        "breakdown": (
            "• **Optional**: `/breakdown [player]:` for another player.\n"
            "• Includes skills, bosses, raids, and clue points.\n"
            "• Separated by multiple pages, use the arrows to navigate."
        ),
        "ingots": (
            "• **Optional**: `/ingots [player]:` to check someone else.\n"
            "• You earn ingots by participating in clan events."
        ),
        "raffle": (
            "• Use `/raffle` to view or enter the raffle.\n"
            "• Use ingots to buy tickets in the raffle channel!"
        ),
        "trick_or_treat": (
            "• Join the seasonal fun with `/trick_or_treat`!\n"
            "• Gain spooky surprises in the `trick_or_treat` channel!"
        ),
    }

    if RAFFLE:
        context["raffle"] += "\n\n🎉 **A raffle is currently active!**"

    all_commands = tree.get_commands()
    all_commands.sort(key=lambda cmd: (cmd.name not in context, cmd.name))

    visible_commands = [
        cmd for cmd in all_commands if cmd.name not in IGNORED_COMMANDS
    ]

    chunk_size = 6
    pages = [
        visible_commands[i : i + chunk_size]
        for i in range(0, len(visible_commands), chunk_size)
    ]

    menu = ViewMenu(
        interaction,
        menu_type=ViewMenu.TypeEmbed,
        show_page_director=True,
        timeout=150,
        delete_on_timeout=True,
    )

    for page_cmds in pages:
        embed = build_response_embed(
            title="📘 Available Commands",
            description="Here’s a list of commands you can use:",
            color=discord.Color.blurple(),
        )

        for cmd in page_cmds:
            extra = context.get(cmd.name)
            description = cmd.description or "No description provided."
            if extra:
                description += f"\n{extra}"

            embed.add_field(
                name=f"/{cmd.name}",
                value=description,
                inline=False,
            )

        menu.add_page(embed)

    menu.add_button(ViewButton.back())
    menu.add_button(ViewButton.next())

    await menu.start()
