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
        "Fine. **{ingots}** is a small price to pay to get out of this interaction.",
        "Congratulations on your life changing payout of **{ingots}**.",
        "You don't deserve this, but I'm feeling generous.\nHere is **{ingots}**, get yourself something nice.",
        "**{ingots}** to trim my armour? You got yourself a deal :handshake:",
        "And now with the recipt of **{ingots}** ingots the contract is official.\nI hope you read the fine print.",
        "I am printing **{ingots}** out of thin air just to make you happy.\nThis devalues all ingots a little bit, I hope you're happy.",
        "If I dropped **{ingots}** north of the Edgeville ditch, would you pick them up?\nAsking for a friend.",
        "When Kodiak's back was turned, I stole **{ingots}** from his account.\nNow they are yours, and you're as guilty as I am.",
        "You have been credited **{ingots}**.\nThank you for playing, human.",
        "On behalf of everyone at Iron Forged I just want to say ~~fuc~~... **congratulations**!!\nWe are all so happy for you.\n**{ingots}**.",
        "Just take **{ingots}** and get out of my sight.",
        "**JACKPOT!!!!!!!**\nOh no, it's only **{ingots}**. False alarm.",
        "**{ingots}** gz.",
        "Gzzzzzzzzzzz!! Winnings: **{ingots}**.",
        "The RNG Gods smile upon you this day, adventurer. **{ingots}**.",
        "You are now thinking about blinking..\nAnd ingots **{ingots}**.",
        "You've been working hard lately. I've noticed.\nTake **{ingots}**",
        "**{ingots}**\n**gzzzzzzz**\ngzzzzzzz\n-# gzzzzzzz",
    ]

    negative_ingot_messages = [
        "You gambled against the house and lost **{ingots}**...\nIt's me. I am the house.",
        "Your profile has been found guilty of botting.\nThe fine is **{ingots}**.\nPayment is mandatory.\nYour guilt is undeinable.",
        "The odds of losing exactly **{ingots}** is truly astronomical.\nReally, you should be proud.",
        "...aaaaaaand it's gone. **{ingots}**",
        "Quick, look behind you! _*yoink*_ **{ingots}**",
        "**JACKPOT!!!!!!!**\nOh no... it's an anti-jackpot **{ingots}**. Unlucky.",
        "You chose...\n\n...poorly **{ingots}**.",
        "Sorry champ, **{ingots}**.",
        "Ah damn, I was rooting for you too **{ingots}**.\n-# not",
        "If you stop reading now, you can pretend you actually won.\n**{ingots}**",
        "**{ingots}**. How cruel of me.",
        "**WRONG {ingots}**, try again.",
        "Ha! **{ingots}**",
        "The RNG Gods are laughing at you **{ingots}**.",
        "**{ingots}** ouch bud.",
        "Unluck pal, **{ingots}**.",
        "You are a loser.\nAlso, you lost **{ingots}** ingots.",
    ]

    ingot_icon = find_emoji(interaction, "Ingot")
    ingot_balance_message = "\n\n**{username}** now has **{total}** ingots."

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

            message = ""
            if random.random() < 0.2:
                message = random.choice(negative_ingot_messages).format(
                    ingots=f"{ingot_icon}{quantity_removed:,}"
                )
            else:
                message = f"You are a loser: **{ingot_icon}{quantity_removed:,}**."

            embed = _build_embed(
                (
                    message
                    + ingot_balance_message.format(
                        username=interaction.user.display_name,
                        total=f"{ingot_icon}{ingot_total:,}",
                    )
                )
            )
            return await interaction.followup.send(embed=embed)
        case TrickOrTreat.ADD_INGOTS_LOW:
            quantity = random.randrange(1, 100, 1) * 10
            quantity_added, ingot_total = await adjust_ingots(
                interaction, quantity, interaction.guild.get_member(interaction.user.id)
            )

            message = ""
            if random.random() < 0.3:
                message = random.choice(positive_ingot_messages).format(
                    ingots=f"{ingot_icon}{quantity_added:,}"
                )
            else:
                message = f"You are a winner! **{ingot_icon}{quantity_added:,}**\ngzzz"

            embed = _build_embed(
                (
                    message
                    + ingot_balance_message.format(
                        username=interaction.user.display_name,
                        total=f"{ingot_icon}{ingot_total:,}",
                    )
                )
            )
            return await interaction.followup.send(embed=embed)
        case TrickOrTreat.REMOVE_INGOTS_HIGH:
            quantity = (random.randrange(100, 250, 1) * 10) * -1
            quantity_removed, ingot_total = await adjust_ingots(
                interaction, quantity, interaction.guild.get_member(interaction.user.id)
            )

            message = ""
            if random.random() < 0.6:
                message = random.choice(negative_ingot_messages).format(
                    ingots=f"{ingot_icon}{quantity_removed:,}"
                )
            else:
                message = (
                    f"Unlucky bud, I'm taking **{ingot_icon}{quantity_removed:,}**."
                )

            embed = _build_embed(
                (
                    message
                    + ingot_balance_message.format(
                        username=interaction.user.display_name,
                        total=f"{ingot_icon}{ingot_total:,}",
                    )
                )
            )
            return await interaction.followup.send(embed=embed)

        case TrickOrTreat.ADD_INGOTS_HIGH:
            quantity = random.randrange(150, 250, 1) * 10
            quantity_added, ingot_total = await adjust_ingots(
                interaction, quantity, interaction.guild.get_member(interaction.user.id)
            )

            message = ""
            if random.random() < 0.3:
                message = random.choice(positive_ingot_messages).format(
                    ingots=f"{ingot_icon}{quantity_added:,}"
                )
            else:
                message = (
                    f"We have a winner!! **{ingot_icon}{quantity_added:,}** big gzzzzz!"
                )

            embed = _build_embed(
                (
                    message
                    + ingot_balance_message.format(
                        username=interaction.user.display_name,
                        total=f"{ingot_icon}{ingot_total:,}",
                    )
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

            embed = ""
            if member.ingots < 1:
                embed = _build_embed(
                    "You lost... well, you would have lost ingots if you had any to lose.\n"
                    "Attend some events, or throw me a bond or something, you're making us look bad. 💀"
                )
            else:
                embed = _build_embed(
                    (
                        f"You lost **{ingot_icon}{member.ingots:,}**... now that's gotta sting."
                        + ingot_balance_message.format(
                            username=interaction.user.display_name,
                            total=f"{ingot_icon}0",
                        )
                    )
                )
            return await interaction.followup.send(embed=embed)

        case TrickOrTreat.JACKPOT_INGOTS:
            if state.trick_or_treat_jackpot_claimed:
                embed = _build_embed(
                    (
                        "**Treat!** Or, well, it would have been... but you have been deemed unworthy.\n"
                        "I don't know what to tell you, I don't make the rules. 🤷‍♂️"
                        "\n\nHave a consolation pumpkin 🎃"
                    )
                )
                return await interaction.followup.send(embed=embed)

            quantity_added, ingot_total = await adjust_ingots(
                interaction,
                1_000_000,
                interaction.guild.get_member(interaction.user.id),
            )

            state.trick_or_treat_jackpot_claimed = True

            embed = _build_embed(
                (
                    f"**JACKPOT!!** 🎉🎊🥳\n\nToday is your lucky day {interaction.user.mention}!\n"
                    f"You have been blessed with the biggest payout I am authorized to give.\n\n"
                    f"A cool **{ingot_icon}{quantity_added:,}** ingots wired directly into your bank account.\n\n"
                    "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                    "`wave2:rainbow:gzzzzzzzzzzzzzzzzzzzzzzzzzzzzz`"
                    + ingot_balance_message.format(
                        username=interaction.user.display_name,
                        total=f"{ingot_icon}{ingot_total:,}",
                    )
                )
            )
            return await interaction.followup.send(embed=embed)


def _build_embed(content: str) -> discord.Embed:
    thumbnails = [
        "https://oldschool.runescape.wiki/images/Pumpkin_detail.png",
        "https://oldschool.runescape.wiki/images/thumb/Jack_lantern_mask_detail.png/1280px-Jack_lantern_mask_detail.png",
        "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern.png/1280px-Jack-O-Lantern.png",
        "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lanterns.png/1280px-Jack-O-Lanterns.png",
        "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%282%29.png/800px-Jack-O-Lantern_%282%29.png",
        "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%285%29.png/1024px-Jack-O-Lantern_%285%29.png",
        "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%286%29.png/1280px-Jack-O-Lantern_%286%29.png",
        "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%288%29.png/1280px-Jack-O-Lantern_%288%29.png",
        "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%289%29.png/1024px-Jack-O-Lantern_%289%29.png",
        "https://oldschool.runescape.wiki/images/thumb/Skull_%28item%29_detail.png/1024px-Skull_%28item%29_detail.png",
    ]
    embed = build_response_embed("", content, discord.Color.orange())
    embed.set_thumbnail(url=random.choice(thumbnails))
    return embed


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
