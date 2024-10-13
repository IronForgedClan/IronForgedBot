import logging
import random
from enum import Enum
from typing import Tuple

import discord

from ironforgedbot.common.helpers import find_emoji, normalize_discord_string
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.state import state
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


class TrickOrTreat(Enum):
    GIF = 5
    REMOVE_INGOTS_LOW = 11
    ADD_INGOTS_LOW = 10
    REMOVE_INGOTS_HIGH = 55
    ADD_INGOTS_HIGH = 50
    REMOVE_ALL_INGOTS_TRICK = 100
    JACKPOT_INGOTS = 10_000


class TrickOrTreatHandler:
    def __init__(self):
        self.weights = [1 / item.value for item in TrickOrTreat]
        self.ingot_icon = find_emoji(None, "Ingot")
        self.gif_history = []
        self.thumbnail_history = []

    def _get_random_positive_message(self) -> str:
        return random.choice(
            [
                "Oh fine.\n**{ingots}** is a small price to pay to get out of this interaction.",
                "Congratulations on your life changing payout of... _*drumroll*_\n**{ingots}**!",
                "I'm feeling generous.\nTake **{ingots}** ingots and get yourself something nice.",
                "**{ingots}** to trim my armour?\nYou got yourself a deal. :handshake:",
                "...and with the recipt of **{ingots}** ingots, the contract is official.\nI hope you read the fine print.",
                "I'm printing **{ingots}** out of thin air just for you.\nThis devalues all ingots a little bit, I hope you're happy.",
                "If I dropped **{ingots}** north of the Edgeville ditch...\nwould you pick them up? Asking for a friend.",
                "When Kodiak's back was turned, I stole **{ingots}** from his account.\nNow they are yours, and you're as guilty as I am.",
                "You have been credited **{ingots}**.\nThank you for playing, human.",
                "On behalf of everyone at Iron Forged I just want to say ~~fuc~~... **congratulations**!!\nWe are all so happy for you. **{ingots}**.",
                "_Sigh_\nJust take **{ingots}** ingots and get out of my sight.",
                "**JACKPOT!!!!!!!**\nOh no, it's only **{ingots}**. False alarm.",
                "**{ingots}**\ngz.",
                "Gzzzzzzzzzzz!!\nWinnings: **{ingots}**.",
                "The RNG Gods smile upon you this day, adventurer.\nYou won **{ingots}** ingots.",
                "You are now thinking about blinking..\n...and ingots **{ingots}**.\n_blingots_.",
                "You've been working hard lately. I've noticed.\nHave **{ingots}** ingots.",
                "**{ingots}**\n**gzzzzzzz**\ngzzzzzzz\n-# gzzzzzzz",
                "You're rich now!\n**{ingots}** ingot payday.",
            ]
        )

    def _get_random_negative_message(self) -> str:
        return random.choice(
            [
                "You gambled against the house and lost **{ingots}**...\nIt's me. I am the house.",
                "Your profile has been found guilty of botting.\nThe fine is **{ingots}**.\nPayment is mandatory.\nYour guilt is undeniable.",
                "The odds of losing exactly **{ingots}** is truly astronomical.\nReally, you should be proud.",
                "...aaaaaaand it's gone. **{ingots}**\n:wave:",
                "Quick, look behind you! _*yoink*_ **{ingots}**\n:eyes:",
                "**JACKPOT!!!!!!!**\nOh no... it's an anti-jackpot **{ingots}**. Unlucky.",
                "You chose...\n\n...poorly **{ingots}**.",
                "Sorry champ..\n**{ingots}** :frowning:",
                "Ah damn, I was rooting for you too **{ingots}**.\n-# not",
                "If you stop reading now, you can pretend you actually won.\n**{ingots}** :hear_no_evil:",
                "**{ingots}**...\nSorry.",
                "**WRONG {ingots}**, try again.\n:person_gesturing_no:",
                "Ha! **{ingots}**\n:person_shrugging:",
                "The RNG Gods are laughing at you, adventurer...\nYou lost **{ingots}** ingots.",
                "**{ingots}** ouch bud.\n:grimacing:",
                "Unluck pal, **{ingots}**.\n:badger:",
                "You are a loser.\n\nAlso, you lost **{ingots}** ingots.",
                "I took no pleasure in deducting **{ingots}** from you.\n... :joy:",
                "The worst part about losing **{ingots}**, isn't the ingot loss.\nIt's the public humiliation. :clown:",
                "It's nothing personal.\nI'm just following my programming **{ingots}**.",
            ]
        )

    def _get_balance_message(self, username: str, balance: int) -> str:
        return f"\n\n**{username}** now has **{self.ingot_icon}{balance:,}** ingots."

    def _build_embed(self, content: str) -> discord.Embed:
        thumbnails = [
            "https://oldschool.runescape.wiki/images/Pumpkin_detail.png",
            "https://oldschool.runescape.wiki/images/thumb/Skull_%28item%29_detail.png/1024px-Skull_%28item%29_detail.png",
            "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%288%29.png/1280px-Jack-O-Lantern_%288%29.png",
            "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%289%29.png/1024px-Jack-O-Lantern_%289%29.png",
            "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%2810%29.png/1024px-Jack-O-Lantern_%2810%29.png",
            "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%2811%29.png/1280px-Jack-O-Lantern_%2811%29.png",
            "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%2812%29.png/1024px-Jack-O-Lantern_%2812%29.png",
            "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%2819%29.png/1024px-Jack-O-Lantern_%2819%29.png",
            "https://oldschool.runescape.wiki/images/thumb/Great_cauldron_%28overflowing%29.png/1280px-Great_cauldron_%28overflowing%29.png",
            "https://oldschool.runescape.wiki/images/thumb/Greater_demon_mask_detail.png/1024px-Greater_demon_mask_detail.png",
            "https://oldschool.runescape.wiki/images/thumb/Black_demon_mask_detail.png/1280px-Black_demon_mask_detail.png",
            "https://oldschool.runescape.wiki/images/thumb/Death.png/1280px-Death.png",
        ]

        chosen_thumbnail = random.choice(
            [s for s in thumbnails if s not in self.thumbnail_history]
        )
        self._add_to_history(chosen_thumbnail, self.thumbnail_history, 8)

        embed = build_response_embed("", content, discord.Color.orange())
        embed.set_thumbnail(url=chosen_thumbnail)
        return embed

    def _build_no_ingots_error_response(self, username: str) -> discord.Embed:
        return self._build_embed(
            (
                f"You lost... well, you would have lost {self.ingot_icon} ingots if you had any to lose.\n"
                + "Attend some events, throw us a bond or _something_.\nYou're making me look bad. 💀"
                + self._get_balance_message(username, 0)
            )
        )

    def _add_to_history(self, item, list: list, limit=5):
        list.append(item)
        if len(list) > limit:
            list.pop(0)

    async def _adjust_ingots(
        self,
        interaction: discord.Interaction,
        quantity: int,
        discord_member: discord.Member | None,
    ) -> Tuple[int | None, int | None]:
        if not discord_member:
            raise Exception("error no user found")

        member = await STORAGE.read_member(
            normalize_discord_string(discord_member.display_name).lower()
        )

        if member is None:
            await send_error_response(
                interaction,
                f"Member '{discord_member.display_name}' not found in storage.",
            )
            return 0, 0

        new_total = member.ingots + quantity

        if new_total < 1 and member.ingots == 0:
            return None, None

        if new_total < 1:
            quantity = member.ingots * -1
            member.ingots = 0
        else:
            member.ingots = new_total

        try:
            await STORAGE.update_members(
                [member], interaction.user.display_name, note="[BOT] Trick or Treat"
            )
        except StorageError as error:
            logger.error(error)
            await send_error_response(interaction, "Error updating ingots.")
            return 0, 0

        return quantity, member.ingots

    async def random_result(self, interaction: discord.Interaction):
        action = random.choices(list(TrickOrTreat), weights=self.weights)[0]

        match action:
            case TrickOrTreat.JACKPOT_INGOTS:
                return await self.result_jackpot(interaction)
            case TrickOrTreat.REMOVE_ALL_INGOTS_TRICK:
                return await self.result_remove_all_ingots_trick(interaction)
            case TrickOrTreat.REMOVE_INGOTS_HIGH:
                return await self.result_remove_high(interaction)
            case TrickOrTreat.ADD_INGOTS_HIGH:
                return await self.result_add_high(interaction)
            case TrickOrTreat.REMOVE_INGOTS_LOW:
                return await self.result_remove_low(interaction)
            case TrickOrTreat.ADD_INGOTS_LOW:
                return await self.result_add_low(interaction)
            case TrickOrTreat.GIF:
                return await self.result_gif(interaction)

    async def result_jackpot(self, interaction: discord.Interaction):
        assert interaction.guild
        if state.trick_or_treat_jackpot_claimed:
            embed = self._build_embed(
                (
                    "**Treat!** Or, well, it would have been... but you have been deemed unworthy.\n"
                    "I don't know what to tell you, I don't make the rules. 🤷‍♂️"
                    "\n\nHave a consolation pumpkin emoji 🎃"
                )
            )
            return await interaction.followup.send(embed=embed)

        quantity_added, ingot_total = await self._adjust_ingots(
            interaction,
            1_000_000,
            interaction.guild.get_member(interaction.user.id),
        )

        state.trick_or_treat_jackpot_claimed = True

        embed = self._build_embed(
            (
                f"**JACKPOT!!** 🎉🎊🥳\n\nToday is your lucky day {interaction.user.mention}!\n"
                f"You have been blessed with the biggest payout I am authorized to give.\n\n"
                f"A cool **{self.ingot_icon}{quantity_added:,}** ingots wired directly into your bank account.\n\n"
                "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                "`wave2:rainbow:gzzzzzzzzzzzzzzzzzzzzzzzzzzzzz`"
                + self._get_balance_message(
                    interaction.user.display_name, ingot_total or 0
                )
            )
        )
        embed.set_thumbnail(
            url="https://oldschool.runescape.wiki/images/thumb/Great_cauldron_%28overflowing%29.png/1280px-Great_cauldron_%28overflowing%29.png"
        )
        return await interaction.followup.send(embed=embed)

    async def result_remove_all_ingots_trick(self, interaction: discord.Interaction):
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
            embed = self._build_no_ingots_error_response(interaction.user.display_name)
        else:
            embed = self._build_embed(
                (
                    f"You lost **{self.ingot_icon}{member.ingots:,}**...\nNow that's gotta sting."
                    + self._get_balance_message(interaction.user.display_name, 0)
                )
            )
        embed.set_thumbnail(
            url="https://oldschool.runescape.wiki/images/thumb/Skull_%28item%29_detail.png/1024px-Skull_%28item%29_detail.png"
        )
        return await interaction.followup.send(embed=embed)

    async def result_remove_high(self, interaction: discord.Interaction):
        assert interaction.guild
        quantity = (random.randrange(100, 250, 1) * 10) * -1
        quantity_removed, ingot_total = await self._adjust_ingots(
            interaction, quantity, interaction.guild.get_member(interaction.user.id)
        )

        if not quantity_removed or not ingot_total:
            await interaction.followup.send(
                embed=self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )
            return

        message = ""
        if random.random() < 0.6:
            message = self._get_random_negative_message().format(
                ingots=f"{self.ingot_icon}{quantity_removed:,}"
            )
        else:
            message = f"Unlucky pal.\nI'm taking **{self.ingot_icon}{quantity_removed:,}** ingots."

        embed = self._build_embed(
            (
                message
                + self._get_balance_message(
                    interaction.user.display_name, ingot_total or 0
                )
            )
        )
        return await interaction.followup.send(embed=embed)

    async def result_add_high(self, interaction: discord.Interaction):
        assert interaction.guild
        quantity = random.randrange(150, 250, 1) * 10
        quantity_added, ingot_total = await self._adjust_ingots(
            interaction, quantity, interaction.guild.get_member(interaction.user.id)
        )

        message = ""
        if random.random() < 0.3:
            message = self._get_random_positive_message().format(
                ingots=f"{self.ingot_icon}{quantity_added:,}"
            )
        else:
            message = f":tada: You won **{self.ingot_icon}{quantity_added:,}** ingots!\ngzzzzzzzzzzzzz :jack_o_lantern:"

        embed = self._build_embed(
            (
                message
                + self._get_balance_message(
                    interaction.user.display_name, ingot_total or 0
                )
            )
        )
        return await interaction.followup.send(embed=embed)

    async def result_remove_low(self, interaction: discord.Interaction):
        assert interaction.guild
        quantity = (random.randrange(1, 100, 1) * 10) * -1
        quantity_removed, ingot_total = await self._adjust_ingots(
            interaction, quantity, interaction.guild.get_member(interaction.user.id)
        )

        if quantity_removed is None and ingot_total is None:
            return await interaction.followup.send(
                embed=self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )

        message = ""
        if random.random() < 0.2:
            message = self._get_random_negative_message().format(
                ingots=f"{self.ingot_icon}{quantity_removed:,}"
            )
        else:
            message = f"Trick! :skull:\n\n**{self.ingot_icon}{quantity_removed:,}**"

        embed = self._build_embed(
            (
                message
                + self._get_balance_message(
                    interaction.user.display_name, ingot_total or 0
                )
            )
        )
        return await interaction.followup.send(embed=embed)

    async def result_add_low(self, interaction: discord.Interaction):
        assert interaction.guild
        quantity = random.randrange(1, 100, 1) * 10
        quantity_added, ingot_total = await self._adjust_ingots(
            interaction, quantity, interaction.guild.get_member(interaction.user.id)
        )

        message = ""
        if random.random() < 0.3:
            message = self._get_random_positive_message().format(
                ingots=f"{self.ingot_icon}{quantity_added:,}"
            )
        else:
            message = f"Nice! You won **{self.ingot_icon}{quantity_added:,}** ingots!\ngzzzzzzzzzzzzz!"

        embed = self._build_embed(
            (
                message
                + self._get_balance_message(
                    interaction.user.display_name, ingot_total or 0
                )
            )
        )
        return await interaction.followup.send(embed=embed)

    async def result_joke(self, interaction: discord.Interaction):
        jokes = [
            "**Why did the skeleton go to the party alone?**\nHe had no body to go with! 🩻"
        ]

        await interaction.followup.send(embed=self._build_embed(random.choice(jokes)))

    async def result_gif(self, interaction: discord.Interaction):
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
            "https://giphy.com/embed/QuxqWk7m9ffxyfoa0a",
            "https://giphy.com/embed/kBrY0BlY4C4jhBeubb",
            "https://giphy.com/embed/qTD9EXZRgI1y0",
        ]

        chosen_gif = random.choice([s for s in gifs if s not in self.gif_history])
        self._add_to_history(chosen_gif, self.gif_history, 10)

        return await interaction.followup.send(chosen_gif)
