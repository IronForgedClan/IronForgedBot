import json
import logging
import random
from enum import Enum
from typing import Optional, List

import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.database.database import db
from ironforgedbot.services.ingot_service import IngotService
from ironforgedbot.services.member_service import MemberService
from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)

# Ingot reward/deduction ranges
LOW_INGOT_MIN = 500
LOW_INGOT_MAX = 2_200
HIGH_INGOT_MIN = 3_200
HIGH_INGOT_MAX = 8_100
JACKPOT_VALUE = 1_000_000

# History limits
POSITIVE_MESSAGE_HISTORY_LIMIT = 10
NEGATIVE_MESSAGE_HISTORY_LIMIT = 10
THUMBNAIL_HISTORY_LIMIT = 15
GIF_HISTORY_LIMIT = 125


class TrickOrTreat(Enum):
    """Enum representing different trick-or-treat outcomes with their probability weights.

    Values represent relative weights (higher value = higher probability).
    Total weight: 1000
    """

    # fmt: off
    GIF = 343                      # 34.3% (1/2.9)
    REMOVE_INGOTS_LOW = 143        # 14.3% (1/7.0)
    ADD_INGOTS_LOW = 137           # 13.7% (1/7.3)
    REMOVE_INGOTS_HIGH = 126       # 12.6% (1/7.9)
    ADD_INGOTS_HIGH = 114          # 11.4% (1/8.8)
    JOKE = 100                     # 10.0% (1/10.0)
    REMOVE_ALL_INGOTS_TRICK = 34   # 3.4% (1/29.4)
    JACKPOT_INGOTS = 3             # 0.3% (1/333.3)
    # fmt: on


class TrickOrTreatHandler:
    """Handler for the trick-or-treat Halloween event minigame.

    Manages random outcomes that add or remove ingots from players,
    with various probabilities and reward/penalty amounts.
    """

    def __init__(self) -> None:
        """Initialize the TrickOrTreatHandler with weighted outcomes and message history."""
        self.weights: List[float] = [item.value for item in TrickOrTreat]
        self.ingot_icon: str = find_emoji("Ingot")
        self.gif_history: List[str] = []
        self.thumbnail_history: List[str] = []
        self.positive_message_history: List[str] = []
        self.negative_message_history: List[str] = []
        self.GIFS: List[str]
        self.THUMBNAILS: List[str]

        with open("data/trick_or_treat.json") as f:
            logger.info("loading trick or treat data...")
            data = json.load(f)

            self.GIFS = data["GIFS"]
            self.THUMBNAILS = data["THUMBNAILS"]

    def _get_random_positive_message(self) -> str:
        """Get a random positive message for when player wins ingots.

        Returns:
            A message template string with {ingots} placeholder.
        """
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
        self._add_to_history(
            chosen, self.positive_message_history, POSITIVE_MESSAGE_HISTORY_LIMIT
        )

        return chosen

    def _get_random_negative_message(self) -> str:
        """Get a random negative message for when player loses ingots.

        Returns:
            A message template string with {ingots} placeholder.
        """
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
        self._add_to_history(
            chosen, self.negative_message_history, NEGATIVE_MESSAGE_HISTORY_LIMIT
        )

        return chosen

    def _get_balance_message(self, username: str, balance: int) -> str:
        """Generate a formatted message showing the user's new ingot balance.

        Args:
            username: The player's display name.
            balance: The new ingot balance.

        Returns:
            A formatted string showing the new balance.
        """
        return f"\n\n**{username}** now has **{self.ingot_icon}{balance:,}** ingots."

    def _build_embed(self, content: str) -> discord.Embed:
        """Build a Discord embed with Halloween-themed styling.

        Args:
            content: The message content to display in the embed.

        Returns:
            A Discord embed with orange color and random thumbnail.
        """
        chosen_thumbnail = random.choice(
            [s for s in self.THUMBNAILS if s not in self.thumbnail_history]
        )
        self._add_to_history(
            chosen_thumbnail, self.thumbnail_history, THUMBNAIL_HISTORY_LIMIT
        )

        embed = build_response_embed("", content, discord.Color.orange())
        embed.set_thumbnail(url=chosen_thumbnail)
        return embed

    def _build_no_ingots_error_response(self, username: str) -> discord.Embed:
        """Build an error embed for when player has no ingots to lose.

        Args:
            username: The player's display name.

        Returns:
            A Discord embed with a humorous error message.
        """
        return self._build_embed(
            (
                "You lost... well, you would have lost ingots if you had any!\n\n"
                + "Attend some events, throw us a bond or _something_. "
                + "You're making me look bad. 💀"
                + self._get_balance_message(username, 0)
            )
        )

    def _add_to_history(
        self, item: str, history_list: List[str], limit: int = 5
    ) -> None:
        """Add an item to a history list, removing oldest if limit exceeded.

        Args:
            item: The item to add to history.
            history_list: The history list to modify.
            limit: Maximum number of items to keep in history.
        """
        history_list.append(item)
        if len(history_list) > limit:
            history_list.pop(0)

    async def _adjust_ingots(
        self,
        interaction: discord.Interaction,
        quantity: int,
        discord_member: Optional[discord.Member],
    ) -> Optional[int]:
        """Add or remove ingots from a player's account.

        Args:
            interaction: The Discord interaction context.
            quantity: Number of ingots to add (positive) or remove (negative).
            discord_member: The Discord member to adjust ingots for.

        Returns:
            The new ingot total if successful, or None if an error occurred
            or if the user has insufficient ingots.
        """
        if not discord_member:
            raise Exception("error no user found")

        async with db.get_session() as session:
            ingot_service = IngotService(session)
            member_service = MemberService(session)

            if quantity > 0:
                result = await ingot_service.try_add_ingots(
                    discord_member.id, quantity, None, "Trick or treat win"
                )
            else:
                member = await member_service.get_member_by_discord_id(
                    discord_member.id
                )

                if not member:
                    logger.error("Member not found in database")
                    await send_error_response(interaction, "Error updating ingots.")
                    return None

                if member.ingots == 0:
                    # User has no ingots to lose
                    return None

                # Adjust quantity if it would make balance negative
                if member.ingots + quantity < 0:
                    quantity = -member.ingots

                result = await ingot_service.try_remove_ingots(
                    discord_member.id, quantity, None, "Trick or treat loss"
                )

            if not result:
                logger.error("Error adjusting ingots")
                await send_error_response(interaction, "Error updating ingots.")
                return None

            if not result.status:
                await send_error_response(interaction, result.message)
                return None

            return result.new_total
        return None

    async def _handle_ingot_result(
        self,
        interaction: discord.Interaction,
        quantity: int,
        is_positive: bool,
    ) -> None:
        """Handle common pattern for adding/removing ingots with appropriate messaging.

        Args:
            interaction: The Discord interaction context.
            quantity: The quantity of ingots (positive for add, negative for remove).
            is_positive: True for positive outcome (win), False for negative (loss).
        """
        assert interaction.guild

        ingot_total = await self._adjust_ingots(
            interaction,
            quantity,
            interaction.guild.get_member(interaction.user.id),
        )

        if ingot_total is None:
            await interaction.followup.send(
                embed=self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )
            return

        message_getter = (
            self._get_random_positive_message
            if is_positive
            else self._get_random_negative_message
        )

        formatted_quantity = f"-{abs(quantity):,}" if quantity < 0 else f"{quantity:,}"
        message = message_getter().format(
            ingots=f"{self.ingot_icon}{formatted_quantity}"
        )

        embed = self._build_embed(
            message
            + self._get_balance_message(interaction.user.display_name, ingot_total)
        )
        await interaction.followup.send(embed=embed)

    async def random_result(self, interaction: discord.Interaction) -> None:
        """Randomly select and execute a trick-or-treat outcome.

        Args:
            interaction: The Discord interaction context.
        """
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
            case TrickOrTreat.JOKE:
                return await self.result_joke(interaction)
            case TrickOrTreat.GIF:
                return await self.result_gif(interaction)

    async def result_jackpot(self, interaction: discord.Interaction) -> None:
        """Award the jackpot prize (1 million ingots) to the player.

        Only one player can claim the jackpot per event. Subsequent attempts
        receive a consolation message.

        Args:
            interaction: The Discord interaction context.
        """
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

        user_new_total = await self._adjust_ingots(
            interaction,
            JACKPOT_VALUE,
            interaction.guild.get_member(interaction.user.id),
        )

        STATE.state["trick_or_treat_jackpot_claimed"] = True

        embed = self._build_embed(
            (
                f"**JACKPOT!!** 🎉🎊🥳\n\nToday is your lucky day "
                f"{interaction.user.mention}!\nYou have been blessed with the "
                "biggest payout I am authorized to give.\n\n"
                f"A cool **{self.ingot_icon}{JACKPOT_VALUE:,}** ingots wired directly "
                "into your bank account.\n\n@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                "`wave2:rainbow:gzzzzzzzzzzzzzzzzzzzzzzzzzzzzz`"
                + self._get_balance_message(
                    interaction.user.display_name, user_new_total or 0
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

    async def result_remove_all_ingots_trick(
        self, interaction: discord.Interaction
    ) -> None:
        """Pretend to remove all ingots from the player (doesn't actually remove them).

        Args:
            interaction: The Discord interaction context.
        """
        assert interaction.guild
        async with db.get_session() as session:
            member_service = MemberService(session)
            member = await member_service.get_member_by_discord_id(interaction.user.id)

            if member is None:
                return await send_error_response(
                    interaction,
                    f"Member '{interaction.user.display_name}' not found in storage.",
                )

            if member.ingots < 1:
                embed = self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            else:
                embed = self._build_embed(
                    (
                        f"You lost **{self.ingot_icon}-{member.ingots:,}**...\n"
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

    async def result_remove_high(self, interaction: discord.Interaction) -> None:
        """Remove a high amount of ingots from the player.

        Args:
            interaction: The Discord interaction context.
        """
        quantity = random.randrange(HIGH_INGOT_MIN, HIGH_INGOT_MAX, 1) * -1
        await self._handle_ingot_result(interaction, quantity, is_positive=False)

    async def result_add_high(self, interaction: discord.Interaction) -> None:
        """Add a high amount of ingots to the player.

        Args:
            interaction: The Discord interaction context.
        """
        quantity = random.randrange(HIGH_INGOT_MIN, HIGH_INGOT_MAX, 1)
        await self._handle_ingot_result(interaction, quantity, is_positive=True)

    async def result_remove_low(self, interaction: discord.Interaction) -> None:
        """Remove a low amount of ingots from the player.

        Args:
            interaction: The Discord interaction context.
        """
        quantity = random.randrange(LOW_INGOT_MIN, LOW_INGOT_MAX, 1) * -1
        await self._handle_ingot_result(interaction, quantity, is_positive=False)

    async def result_add_low(self, interaction: discord.Interaction) -> None:
        """Add a low amount of ingots to the player.

        Args:
            interaction: The Discord interaction context.
        """
        quantity = random.randrange(LOW_INGOT_MIN, LOW_INGOT_MAX, 1)
        await self._handle_ingot_result(interaction, quantity, is_positive=True)

    async def result_joke(self, interaction: discord.Interaction) -> None:
        """Send a random Halloween-themed joke (currently unused).

        Args:
            interaction: The Discord interaction context.
        """
        jokes = [
            "**Why did the skeleton go to the party alone?**\n"
            "He had no body to go with! 🩻"
        ]

        await interaction.followup.send(embed=self._build_embed(random.choice(jokes)))

    async def result_gif(self, interaction: discord.Interaction) -> None:
        """Send a random Halloween-themed GIF.

        Args:
            interaction: The Discord interaction context.
        """
        chosen_gif = random.choice([s for s in self.GIFS if s not in self.gif_history])
        self._add_to_history(chosen_gif, self.gif_history, GIF_HISTORY_LIMIT)

        return await interaction.followup.send(chosen_gif)


# Module-level handler instance cache
_handler_instance: Optional[TrickOrTreatHandler] = None


def get_handler() -> TrickOrTreatHandler:
    """Get the singleton TrickOrTreatHandler instance.

    Uses lazy initialization to create the handler only once and cache it
    for subsequent calls. This avoids reloading JSON data and maintains
    message/GIF history across multiple command invocations.

    Returns:
        The cached TrickOrTreatHandler instance.
    """
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = TrickOrTreatHandler()
    return _handler_instance
