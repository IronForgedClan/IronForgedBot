import json
import logging
import random
from enum import Enum

import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.database.database import db
from ironforgedbot.decorators import singleton
from ironforgedbot.services.ingot_service import IngotService
from ironforgedbot.services.member_service import MemberService
from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)


class TrickOrTreat(Enum):
    GIF = 5
    REMOVE_INGOTS_LOW = 11
    ADD_INGOTS_LOW = 10
    REMOVE_INGOTS_HIGH = 55
    ADD_INGOTS_HIGH = 50
    REMOVE_ALL_INGOTS_TRICK = 100
    JACKPOT_INGOTS = 10_000


@singleton
class TrickOrTreatHandler:
    def __init__(self):
        self.weights = [1 / item.value for item in TrickOrTreat]
        self.ingot_icon = find_emoji("Ingot")
        self.gif_history = []
        self.thumbnail_history = []
        self.positive_message_history = []
        self.negative_message_history = []

        with open("data/trick_or_treat.json") as f:
            logger.info("loading trick or treat data...")
            data = json.load(f)

            self.GIFS = data["GIFS"]
            self.THUMBNAILS = data["THUMBNAILS"]

    def _get_random_positive_message(self) -> str:
        if random.random() >= 0.5:
            return ":tada: Treat! **{ingots}**!\ngzzzzzzzzzzzzz :jack_o_lantern:"

        options = [
            (
                "Oh fine.\n**{ingots}** is a small price to pay to get "
                "out of this interaction."
            ),
            (
                "Congratulations on your life changing payout of... "
                "_*drumroll*_\n**{ingots}**!"
            ),
            (
                "I'm feeling generous.\nTake **{ingots}** ingots and "
                "get yourself something nice."
            ),
            "**{ingots}** to trim my armour?\nYou got yourself a deal. :handshake:",
            (
                "...and with the recipt of **{ingots}** ingots, the contract is "
                "official.\nI hope you read the fine print."
            ),
            (
                "I'm printing **{ingots}** out of thin air just for you.\n"
                "This devalues all ingots a little bit, I hope you're happy."
            ),
            (
                "If I dropped **{ingots}** north of the Edgeville ditch...\n"
                "would you pick them up? Asking for a friend."
            ),
            (
                "When Kodiak's back was turned, I stole **{ingots}** from his "
                "account.\nNow they are yours, and you're as guilty as I am."
            ),
            "You have been credited **{ingots}**.\nThank you for playing, human.",
            (
                "On behalf of everyone at Iron Forged I just want to say ~~fuc~~... "
                "**congratulations**!!\nWe are all so happy for you. **{ingots}**."
            ),
            "_Sigh_\nJust take **{ingots}** ingots and get out of my sight.",
            "**JACKPOT!!!!!!!**\nOh no, it's only **{ingots}**. False alarm.",
            "**{ingots}**\ngz.",
            "Gzzzzzzzzzzz!!\nWinnings: **{ingots}**.",
            (
                "The RNG Gods smile upon you this day, adventurer.\n"
                "You won **{ingots}** ingots."
            ),
            (
                "You are now thinking about blinking..\n"
                "...and ingots **{ingots}**.\n_blingots_."
            ),
            (
                "You've been working hard lately. I've noticed.\n"
                "Have **{ingots}** ingots."
            ),
            "**{ingots}**\n**gzzzzzzz**\ngzzzzzzz\n-# gzzzzzzz",
            "You're rich now!\n**{ingots}** ingot payday.",
            "Good job bud!\n**{ingots}**.",
            "Hey bud!\n**{ingots}** you deserve this.",
            (
                "Good day adventurer. I come to you with gifts.\n"
                "**{ingots}** fresh from the mine."
            ),
            "**{ingots}** just for you,\nbud.",
            "**{ingots}** from my bud **test run btw**\ndirectly to you!",
        ]

        chosen = random.choice(
            [s for s in options if s not in self.positive_message_history]
        )
        self._add_to_history(chosen, self.positive_message_history, 5)

        return chosen

    def _get_random_negative_message(self) -> str:
        if random.random() >= 0.5:
            annoyance = [
                "bud",
                "buddy",
                "pal",
                "champ",
                "boss",
                "chief",
                "friend",
                "mate",
                "kid",
                "kiddo",
            ]
            return (
                "Trick!\nUnlucky " + random.choice(annoyance) + " **{ingots}** ingots."
            )

        options = [
            (
                "You gambled against the house and lost **{ingots}**...\n"
                "It's me. I am the house."
            ),
            (
                "Your profile has been found guilty of botting.\nThe fine is "
                "**{ingots}**.\nPayment is mandatory.\nYour guilt is undeniable."
            ),
            (
                "The odds of losing exactly **{ingots}** is truly astronomical.\n"
                "Really, you should be proud."
            ),
            "...aaaaaaand it's gone.\n**{ingots}** :wave:",
            "Quick, look behind you! _*yoink*_ **{ingots}**\n:eyes:",
            "**JACKPOT!!!!!!!**\nOh no... it's an anti-jackpot **{ingots}**. Unlucky.",
            "You chose...\n\n...poorly **{ingots}**.",
            "Sorry champ..\n**{ingots}** :frowning:",
            "Ah damn, I was rooting for you too **{ingots}**.\n-# not",
            (
                "If you stop reading now, you can pretend you actually won.\n"
                "**{ingots}** :hear_no_evil:"
            ),
            "**{ingots}**...\nSorry.",
            "**WRONG {ingots}**, try again.\n:person_gesturing_no:",
            "Ha!\n**{ingots}** :person_shrugging:",
            (
                "The RNG Gods are laughing at you, adventurer...\n"
                "You lost **{ingots}** ingots."
            ),
            "**{ingots}** ouch bud.\n:grimacing:",
            "Unluck pal, **{ingots}**.\n:badger:",
            "You are a loser.\n\nAlso, you lost **{ingots}** ingots.",
            "I took no pleasure in deducting **{ingots}** from you.\n... :joy:",
            (
                "The worst part about losing **{ingots}**, isn't the ingot loss.\n"
                "It's the public humiliation. :clown:"
            ),
            "It's nothing personal.\nI'm just following my programming **{ingots}**.",
            "Sorry bud...\n**{ingots}**",
            "Sorry buddy...\n**{ingots}**",
            "Unlucky bud...\n**{ingots}**",
            "Sucks to be you, champ.\n**{ingots}**",
            "My electricity bill is due...\nIt's your turn **{ingots}**.",
            "I see dead ingots.\n**{ingots}** :ghost:",
        ]

        chosen = random.choice(
            [s for s in options if s not in self.negative_message_history]
        )
        self._add_to_history(chosen, self.negative_message_history, 5)

        return chosen

    def _get_balance_message(self, username: str, balance: int) -> str:
        return f"\n\n**{username}** now has **{self.ingot_icon}{balance:,}** ingots."

    def _build_embed(self, content: str) -> discord.Embed:
        chosen_thumbnail = random.choice(
            [s for s in self.THUMBNAILS if s not in self.thumbnail_history]
        )
        self._add_to_history(chosen_thumbnail, self.thumbnail_history, 8)

        embed = build_response_embed("", content, discord.Color.orange())
        embed.set_thumbnail(url=chosen_thumbnail)
        return embed

    def _build_no_ingots_error_response(self, username: str) -> discord.Embed:
        return self._build_embed(
            (
                "You lost... _well_, you would have lost ingots if you had any!\n"
                + "Attend some events, throw us a bond or _something_.\n"
                + "You're making me look bad. 💀"
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
    ) -> int:
        if not discord_member:
            raise Exception("error no user found")

        async for session in db.get_session():
            ingot_service = IngotService(session)
            member_service = MemberService(session)

            if quantity > 0:
                result = await ingot_service.try_add_ingots(
                    discord_member.id, quantity, None, "Trick or treat win"
                )
            else:
                member = await member_service.get_member_by_discord_id(
                    interaction.user.id
                )

                if not member:
                    logger.error("Member not found in database")
                    await send_error_response(interaction, "Error updating ingots.")
                    return 0

                if member.ingots > 0 and member.ingots - quantity < 0:
                    quantity = member.ingots
                else:
                    return -1

                result = await ingot_service.try_remove_ingots(
                    discord_member.id, quantity, None, "Trick or treat loss"
                )

            if not result:
                logger.error("Error adjusting ingots")
                await send_error_response(interaction, "Error updating ingots.")
                return 0

            if not result.status:
                await send_error_response(interaction, result.message)
                return 0

            return result.new_total
        return 0

    async def random_result(self, interaction: discord.Interaction):
        match random.choices(list(TrickOrTreat), weights=self.weights)[0]:
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
        if STATE.state["trick_or_treat_jackpot_claimed"]:
            embed = self._build_embed(
                (
                    "**Treat!** Or, well, it would have been... but you have been "
                    "deemed unworthy.\nI don't know what to tell you, I don't "
                    "make the rules. 🤷‍♂️"
                    "\n\nHave a consolation pumpkin emoji 🎃"
                )
            )
            return await interaction.followup.send(embed=embed)

        jackpot_value = 1_000_000

        user_new_total = await self._adjust_ingots(
            interaction,
            jackpot_value,
            interaction.guild.get_member(interaction.user.id),
        )

        STATE.state["trick_or_treat_jackpot_claimed"] = True

        embed = self._build_embed(
            (
                f"**JACKPOT!!** 🎉🎊🥳\n\nToday is your lucky day "
                f"{interaction.user.mention}!\nYou have been blessed with the "
                "biggest payout I am authorized to give.\n\n"
                f"A cool **{self.ingot_icon}{jackpot_value:,}** ingots wired directly "
                "into your bank account.\n\n@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                "`wave2:rainbow:gzzzzzzzzzzzzzzzzzzzzzzzzzzzzz`"
                + self._get_balance_message(
                    interaction.user.display_name, user_new_total
                )
            )
        )
        embed.set_thumbnail(
            url=(
                "https://oldschool.runescape.wiki/images/thumb/"
                "Great_cauldron_%28overflowing%29.png"
                "/1280px-Great_cauldron_%28overflowing%29.png"
            )
        )
        return await interaction.followup.send(embed=embed)

    async def result_remove_all_ingots_trick(self, interaction: discord.Interaction):
        async for session in db.get_session():
            member_service = MemberService(session)
            member = await member_service.get_member_by_discord_id(interaction.user.id)

            if member is None:
                return await send_error_response(
                    interaction,
                    f"Member '{interaction.user.display_name}' not found in storage.",
                )

            embed = ""
            if member.ingots < 1:
                embed = self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            else:
                embed = self._build_embed(
                    (
                        f"You lost **{self.ingot_icon}{member.ingots:,}**...\n"
                        "Now that's gotta sting."
                        + self._get_balance_message(interaction.user.display_name, 0)
                    )
                )
            embed.set_thumbnail(
                url=(
                    "https://oldschool.runescape.wiki/images/thumb/"
                    "Skull_%28item%29_detail.png/1024px-Skull_%28item%29_detail.png"
                )
            )
            return await interaction.followup.send(embed=embed)

    async def result_remove_high(self, interaction: discord.Interaction):
        assert interaction.guild
        quantity_removed = (random.randrange(100, 250, 1) * 10) * -1

        ingot_total = await self._adjust_ingots(
            interaction,
            quantity_removed,
            interaction.guild.get_member(interaction.user.id),
        )

        if ingot_total < 0:
            await interaction.followup.send(
                embed=self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )
            return

        message = self._get_random_negative_message().format(
            ingots=f"{self.ingot_icon}{quantity_removed:,}"
        )

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
        quantity_added = random.randrange(150, 250, 1) * 10
        ingot_total = await self._adjust_ingots(
            interaction,
            quantity_added,
            interaction.guild.get_member(interaction.user.id),
        )

        message = self._get_random_positive_message().format(
            ingots=f"{self.ingot_icon}{quantity_added:,}"
        )

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
        quantity_removed = (random.randrange(1, 100, 1) * 10) * -1
        ingot_total = await self._adjust_ingots(
            interaction,
            quantity_removed,
            interaction.guild.get_member(interaction.user.id),
        )

        if ingot_total < 0:
            return await interaction.followup.send(
                embed=self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )

        message = self._get_random_negative_message().format(
            ingots=f"{self.ingot_icon}{quantity_removed:,}"
        )

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
        quantity_added = random.randrange(1, 100, 1) * 10
        ingot_total = await self._adjust_ingots(
            interaction,
            quantity_added,
            interaction.guild.get_member(interaction.user.id),
        )

        message = self._get_random_positive_message().format(
            ingots=f"{self.ingot_icon}{quantity_added:,}"
        )

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
            "**Why did the skeleton go to the party alone?**\n"
            "He had no body to go with! 🩻"
        ]

        await interaction.followup.send(embed=self._build_embed(random.choice(jokes)))

    async def result_gif(self, interaction: discord.Interaction):
        chosen_gif = random.choice([s for s in self.GIFS if s not in self.gif_history])
        self._add_to_history(chosen_gif, self.gif_history, 100)

        return await interaction.followup.send(chosen_gif)
