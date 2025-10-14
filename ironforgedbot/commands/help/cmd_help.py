import discord
from discord import app_commands
from reactionmenu import ViewMenu, ViewButton

from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators import require_role
from ironforgedbot.config import CONFIG, ENVIRONMENT
from ironforgedbot.state import STATE


@require_role(ROLE.MEMBER)
async def cmd_help(interaction: discord.Interaction):
    tree = interaction.client.tree

    user_role_names = {role.name for role in interaction.user.roles}
    has_leadership = "Leadership" in user_role_names
    has_member = "Member" in user_role_names or has_leadership

    commands = tree.get_commands(guild=None)
    commands.sort(key=lambda cmd: cmd.name)

    leadership_only_commands = {
        "admin", "get_role_members", "raffle", "add_remove_ingots", "roster"
    }

    debug_only_commands = {
        "debug_commands", "debug_error_report", "stress_test"
    }

    visible_commands = []
    for cmd in commands:
        if cmd.name in leadership_only_commands and not has_leadership:
            continue
        if cmd.name in debug_only_commands and CONFIG.ENVIRONMENT not in (
            ENVIRONMENT.DEVELOPMENT,
            ENVIRONMENT.STAGING,
        ):
            continue
        visible_commands.append(cmd)

    chunk_size = 4
    pages = [
        visible_commands[i : i + chunk_size] for i in range(0, len(visible_commands), chunk_size)
    ]

    menu = ViewMenu(
        interaction,
        menu_type=ViewMenu.TypeEmbed,
        show_page_director=True,
        timeout=300,
        delete_on_timeout=True,
    )

    for page_cmds in pages:
        embed = discord.Embed(
            title="📘 Available Commands",
            description="Here’s a list of commands you can use:",
            color=discord.Color.blurple(),
        )

        for cmd in page_cmds:
            embed.add_field(
                name=f"/{cmd.name}",
                value=cmd.description or "No description provided.",
                inline=False,
            )

        menu.add_page(embed)

    usage_embed = discord.Embed(
        title="Getting Started with Iron Forged Bot",
        description="Helpful tips to get the most out of the bot.",
        color=discord.Color.gold(),
    )

    usage_embed.add_field(
        name="/score",
        value=(
            "Displays your clan score.\n"
            "• **Optional**: `/score player:` to check another player's score.\n"
            "• If omitted, it will default to your nickname.\n"
            "• Score is based on skilling, bossing, raids, and clue completion."
        ),
        inline=False,
    )

    usage_embed.add_field(
        name="/breakdown",
        value=(
            "Gives a full breakdown of your score.\n"
            "• **Optional**: `/breakdown player:` for another player.\n"
            "• Includes skills, bosses, raids, and clue points.\n"
            "• Separated by multiple pages, use the arrows to navigate through them."
        ),
        inline=False,
    )

    usage_embed.add_field(
        name="/ingots",
        value=(
            "Shows how many ingots you (or another player) have.\n"
            "• **Optional**: `/ingots player:` to check someone else.\n"
            "• You earn ingots by participating in clan events. \n"
        ),
        inline=False,
    )

    if STATE.state.get("raffle_on", False):
        usage_embed.add_field(
            name="🎟️ Raffle Active!",
            value=(
                "A raffle is currently running!\n"
                "Use `/raffle` to view or enter the raffle.\n"
                "Use ingots to buy tickets in the raffle channel!"
            ),
            inline=False,
        )

    if CONFIG.TRICK_OR_TREAT_ENABLED:
        usage_embed.add_field(
            name="🎃 Trick or Treat Event Active!",
            value=(
                "Join the seasonal fun with `/trick_or_treat`!\n"
                "Gain spooky surprises in the trick_or_treat channel!"
            ),
            inline=False,
        )

    menu.add_page(usage_embed)

    menu.add_button(ViewButton.back())
    menu.add_button(ViewButton.next())

    await menu.start()
