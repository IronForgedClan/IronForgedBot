import logging
import random

import discord
from discord import app_commands

from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators import require_role

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER)
@log_command_execution(logger)
async def cmd_rng_reset(interaction: discord.Interaction):
    """Reset your RNG with a 50/50 success rate.

    Arguments:
        interaction: Discord Interaction from CommandTree.
    """
    is_success = random.random() < 0.5

    if is_success:
        embed = build_response_embed(
            title="RNG Reset Successful!",
            description="Your RNG has been restored. That pet is definitely dropping on your next kill. Probably.",
            color=discord.Colour.green(),
        )
        embed.set_thumbnail(
            url="https://oldschool.runescape.wiki/images/thumb/Reward_casket_%28master%29.png/150px-Reward_casket_%28master%29.png"
        )
    else:
        embed = build_response_embed(
            title="You rolled a 0!",
            description="The RNG gods have denied your request. Enjoy staying dry for another 10,000 kills.",
            color=discord.Colour.red(),
        )
        embed.set_thumbnail(
            url="https://oldschool.runescape.wiki/images/thumb/Skull.png/130px-Skull.png"
        )

    await interaction.followup.send(embed=embed)
