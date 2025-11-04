import asyncio
import logging
import random

import discord

from ironforgedbot.common.logging_utils import log_command_execution
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.roles import ROLE
from ironforgedbot.decorators.command_price import command_price
from ironforgedbot.decorators.require_role import require_role

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER)
@command_price(999)
@log_command_execution(logger)
async def cmd_reset_rng(interaction: discord.Interaction):
    """Reset your RNG with a 50/50 success rate.

    Arguments:
        interaction: Discord Interaction from CommandTree.
    """
    is_lucky = random.random() < 0.5

    dice_image_url = (
        "https://oldschool.runescape.wiki/images/thumb/Dice_(6).png/245px-Dice_(6).png"
    )

    dice_embed = discord.Embed(
        description=f"### {interaction.user.mention} is rolling for an RNG reset...",
        color=discord.Colour.blurple(),
    )
    dice_embed.set_image(url=dice_image_url)

    dice_message = await interaction.followup.send(embed=dice_embed)

    await asyncio.sleep(5)

    await dice_message.delete()

    if is_lucky:
        result_embed = build_response_embed(
            title="RNG Reset Successful!",
            description="Your RNG has been restored. That pet is definitely dropping on your next kill. Probably.",
            color=discord.Colour.green(),
        )
        result_embed.set_thumbnail(
            url="https://oldschool.runescape.wiki/images/thumb/Reward_casket_%28master%29.png/150px-Reward_casket_%28master%29.png"
        )
    else:
        result_embed = build_response_embed(
            title="You rolled a 0!",
            description="The RNG gods have denied your request. Enjoy staying dry for another 10,000 kills.",
            color=discord.Colour.red(),
        )
        result_embed.set_thumbnail(
            url="https://oldschool.runescape.wiki/images/thumb/Skull.png/130px-Skull.png"
        )

    await interaction.followup.send(embed=result_embed)
