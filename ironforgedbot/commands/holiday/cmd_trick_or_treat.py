import logging
import random
from enum import Enum
from typing import Tuple

import discord

from ironforgedbot.state import state
from ironforgedbot.common.helpers import find_emoji, normalize_discord_string
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLES
from ironforgedbot.decorators import require_role
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


class TrickOrTreat(Enum):
    JOKE = 1
    GIF = 2
    REMOVE_INGOTS_LOW = 3
    ADD_INGOTS_LOW = 4
    REMOVE_INGOTS_HIGH = 5
    ADD_INGOTS_HIGH = 6
    REMOVE_ALL_INGOTS_TRICK = 7
    JACKPOT_INGOTS = 8

    @property
    def weight(self):
        return self.value


@require_role(ROLES.ANY)
async def cmd_trick_or_treat(interaction: discord.Interaction):
    assert interaction.guild
    trick_or_treat = [item for item in TrickOrTreat]
    weights = [item.weight for item in TrickOrTreat]

    action = random.choices(trick_or_treat, weights)[0]

    positive_ingot_messages = [
        "I give you {ingots}, and you give me your undying loyalty.\nOh you agree? That was easy.",
        "Congratulations on your life changing payout of {ingots}.",
        "You don't deserve this, but I'm feeling generous. Here is {ingots}, get yourself something nice.",
        "So if I give you {ingots}, you will trim my armour?\n\n**Deal!**",
        "With the recipt of {ingots}, you pledge to tattoo the Iron Forged logo on your forehead.\n\nNo takesy-backsies.",
    ]

    negative_ingot_messages = [
        "You gambled against the house and lost {ingots}... duh!",
        "Your account has been found guilty of RWT. You will now pay the {ingot} penalty.\nWe shall never speak of this again.",
        "The odds of losing exactly {ingots} is astronomical. Really, you should be proud.",
    ]

    match action:
        case TrickOrTreat.JOKE:
            return await send_joke(interaction)
        case TrickOrTreat.GIF:
            return await send_gif(interaction)
        case TrickOrTreat.REMOVE_INGOTS_LOW:
            quantity = (random.randrange(1, 100, 1) * 10) * -1

            quantity_removed, ingot_total = await adjust_ingots(
                interaction, quantity, interaction.guild.get_member(interaction.user.id)
            )

            ingot_icon = find_emoji(interaction, "Ingot")
            embed = _build_embed(
                (
                    f"**Trick!** 💀\nYou gambled, and __lost__ **{ingot_icon}{abs(quantity_removed):,}**"
                    f"... sucks to be you, bud."
                    f"\n\n{interaction.user.display_name} now has **{ingot_total:,}** ingots."
                )
            )
            return await interaction.followup.send(embed=embed)
        case TrickOrTreat.ADD_INGOTS_LOW:
            quantity = random.randrange(1, 100, 1) * 10

            quantity_added, ingot_total = await adjust_ingots(
                interaction, quantity, interaction.guild.get_member(interaction.user.id)
            )

            ingot_icon = find_emoji(interaction, "Ingot")
            embed = _build_embed(
                (
                    f"**Treat!** 🥳\nNow, if I give you **{ingot_icon}{quantity_added:,}**,"
                    "promise me you won't spend them all at once!"
                    f"\n\n{interaction.user.display_name} now has **{ingot_total:,}** ingots."
                )
            )
            return await interaction.followup.send(embed=embed)
        case TrickOrTreat.ADD_INGOTS_HIGH:
            quantity = random.randrange(100, 250, 1) * 10

            quantity_added, ingot_total = await adjust_ingots(
                interaction, quantity, interaction.guild.get_member(interaction.user.id)
            )

            ingot_icon = find_emoji(interaction, "Ingot")
            embed = _build_embed(
                f"**Treat!** 🎉\nYou won a massive payout of **{ingot_icon}{quantity_added:,}**... gzzzzzz!"
                f"\n\n{interaction.user.display_name} now has **{ingot_total:,}** ingots."
            )
            return await interaction.followup.send(embed=embed)
        case TrickOrTreat.REMOVE_INGOTS_HIGH:
            quantity = (random.randrange(100, 250, 1) * 10) * -1

            quantity_removed, ingot_total = await adjust_ingots(
                interaction, quantity, interaction.guild.get_member(interaction.user.id)
            )

            ingot_icon = find_emoji(interaction, "Ingot")
            embed = _build_embed(
                (
                    f"**Trick!** 💀\nYou lost **{ingot_icon}{abs(quantity_removed):,}**... ouch, bud. Big yikes my guy."
                    f"\n\n{interaction.user.display_name} now has **{ingot_total:,}** ingots."
                )
            )
            return await interaction.followup.send(embed=embed)
        case TrickOrTreat.REMOVE_ALL_INGOTS_TRICK:
            member = await STORAGE.read_member(
                normalize_discord_string(interaction.user.display_name).lower()
            )

            if member is None:
                return await send_error_response(
                    interaction,
                    f"Member '{interaction.user.display_name}' not found in storage.",
                )

            ingot_icon = find_emoji(interaction, "Ingot")
            embed = ""
            if member.ingots < 1:
                embed = _build_embed(
                    "**Trick!** 💀\nYou lost... well, you would have lost ingots if you had any to lose.\n"
                    "Attend some events, or throw me a bond or something, you're making us look bad. 💀"
                )
            else:
                embed = _build_embed(
                    f"**Trick!** 💀\nYou lost **{ingot_icon}{member.ingots:,}**... oof, that's gotta sting."
                    f"\n\n{interaction.user.display_name} now has **0** ingots."
                )
            return await interaction.followup.send(embed=embed)

        case TrickOrTreat.JACKPOT_INGOTS:
            if state.trick_or_treat_jackpot_claimed:
                embed = _build_embed(
                    (
                        "**Treat!** 🎉\nOr, well, it would have been... but you have been deemed unworthy.\n"
                        "I don't know what to tell you, I don't make the rules. 🤷‍♂️"
                        "\n\nHave a consolation pumpkin: 🎃"
                    )
                )
                return await interaction.followup.send(embed=embed)

            quantity_added, ingot_total = await adjust_ingots(
                interaction,
                1_000_000,
                interaction.guild.get_member(interaction.user.id),
            )

            state.trick_or_treat_jackpot_claimed = True

            ingot_icon = find_emoji(interaction, "Ingot")
            embed = _build_embed(
                (
                    f"**JACKPOT!!** 🎉🎊🥳\n\nToday is your lucky day {interaction.user.mention}!\n"
                    f"You have been blessed with **{ingot_icon}{quantity_added:,}** ingots...\n"
                    "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@"
                    "wave2:rainbow:gzzzzzzzzzzzzzzzzzzzzzzzz!!"
                    f"\n\n{interaction.user.display_name} now rich, with **{ingot_total:,}** ingots total."
                )
            )
            return await interaction.followup.send(embed=embed)


def _build_embed(content: str) -> discord.Embed:
    return build_response_embed("", content, discord.Color.orange())


async def send_joke(interaction: discord.Interaction):
    jokes = [
        "**Why did the skeleton go to the party alone?**\nHe had no body to go with! 🩻"
    ]

    await interaction.followup.send(embed=_build_embed(random.choice(jokes)))


async def send_gif(interaction: discord.Interaction):
    gifs = [
        "https://giphy.com/embed/jbJYmyIdelAJh9LQPs",
        "https://giphy.com/embed/l3vRfhFD8hJCiP0uQ",
        "https://giphy.com/embed/Z4Sek3StLGVO0",
        "https://giphy.com/embed/RokPlX3C71piryApkp",
        "https://giphy.com/embed/NOxZHqpeAw9tm",
        "https://giphy.com/embed/n8bAozpJjeiMU",
        "https://giphy.com/embed/RIHJGMww0p2IZng2l9",
        "https://giphy.com/embed/5yeQRdiYrDq2A",
        "https://giphy.com/embed/69warOL5MBhyzjAMov",
        "https://giphy.com/embed/7JbMfrLQJmxUc",
        "https://giphy.com/embed/26tjZAwU4fAQaahe8",
        "https://giphy.com/embed/cHw5gruhGb0IM",
        "https://giphy.com/embed/T9PbAsiKKWYlG",
        "https://giphy.com/embed/l0HlQXkh1wx1RjtUA",
        "https://giphy.com/embed/KupdfnqWwV7J6",
        "https://giphy.com/embed/RwLDkna2fN3fG",
        "https://giphy.com/embed/fvxGJE7bvJ6I5YJm4a",
        "https://giphy.com/embed/3ohjV8JRMcNVGYK10I",
        "https://giphy.com/embed/5fOiRnJOUnTMY",
        "https://giphy.com/embed/oS5Uanjai8qbe",
        "https://giphy.com/embed/oVmJpctjWDmi4",
    ]
    await interaction.followup.send(random.choice(gifs))


async def adjust_ingots(
    interaction: discord.Interaction,
    quantity: int,
    discord_member: discord.Member | None,
) -> Tuple[int, int]:
    if not discord_member:
        raise Exception("error no user found")

    member = await STORAGE.read_member(
        normalize_discord_string(discord_member.display_name).lower()
    )

    if member is None:
        await send_error_response(
            interaction, f"Member '{discord_member.display_name}' not found in storage."
        )
        return 0, 0

    new_total = member.ingots + quantity

    if new_total < 1:
        quantity = member.ingots
        member.ingots = 0
    else:
        member.ingots = new_total

    try:
        await STORAGE.update_members(
            [member], interaction.user.display_name, note="[BOT] Trick or Treat"
        )
    except StorageError as error:
        await send_error_response(interaction, f"Error updating ingots: {error}")
        return 0, 0

    return quantity, member.ingots
