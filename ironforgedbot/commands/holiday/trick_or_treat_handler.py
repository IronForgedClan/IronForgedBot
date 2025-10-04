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
    GIF = 337                      # 33.7% (1/3.0)
    REMOVE_INGOTS_LOW = 150        # 15.0% (1/6.7)
    ADD_INGOTS_LOW = 140           # 14.0% (1/7.1)
    REMOVE_INGOTS_HIGH = 130       # 13.0% (1/7.7)
    ADD_INGOTS_HIGH = 120          # 12.0% (1/8.3)
    JOKE = 100                     # 10.0% (1/10.0)
    REMOVE_ALL_INGOTS_TRICK = 20   #  2.0% (1/50.0)
    JACKPOT_INGOTS = 3             #  0.3% (1/333.3)
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

        # Data loaded from JSON
        self.GIFS: List[str]
        self.THUMBNAILS: List[str]
        self.POSITIVE_MESSAGES: List[str]
        self.NEGATIVE_MESSAGES: List[str]
        self.NEGATIVE_ANNOYANCES: List[str]
        self.JOKES: List[str]
        self.NO_INGOTS_MESSAGE: str
        self.JACKPOT_SUCCESS_PREFIX: str
        self.JACKPOT_CLAIMED_MESSAGE: str
        self.REMOVE_ALL_TRICK_MESSAGE: str

        with open("data/trick_or_treat.json") as f:
            logger.info("loading trick or treat data...")
            data = json.load(f)

            self.GIFS = data["GIFS"]
            self.THUMBNAILS = data["THUMBNAILS"]
            self.POSITIVE_MESSAGES = data["POSITIVE_MESSAGES"]
            self.NEGATIVE_MESSAGES = data["NEGATIVE_MESSAGES"]
            self.NEGATIVE_ANNOYANCES = data["NEGATIVE_ANNOYANCES"]
            self.JOKES = data["JOKES"]
            self.NO_INGOTS_MESSAGE = data["NO_INGOTS_MESSAGE"]
            self.JACKPOT_SUCCESS_PREFIX = data["JACKPOT_SUCCESS_PREFIX"]
            self.JACKPOT_CLAIMED_MESSAGE = data["JACKPOT_CLAIMED_MESSAGE"]
            self.REMOVE_ALL_TRICK_MESSAGE = data["REMOVE_ALL_TRICK_MESSAGE"]

    def _get_random_positive_message(self) -> str:
        """Get a random positive message for when player wins ingots.

        Returns:
            A message template string with {ingots} placeholder.
        """
        chosen = random.choice(
            [s for s in self.POSITIVE_MESSAGES if s not in self.positive_message_history]
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
            return (
                "Trick!\nUnlucky "
                + random.choice(self.NEGATIVE_ANNOYANCES)
                + " **{ingots}** ingots."
            )

        chosen = random.choice(
            [s for s in self.NEGATIVE_MESSAGES if s not in self.negative_message_history]
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
            self.NO_INGOTS_MESSAGE + self._get_balance_message(username, 0)
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
            embed = self._build_embed(self.JACKPOT_CLAIMED_MESSAGE)
            return await interaction.followup.send(embed=embed)

        user_new_total = await self._adjust_ingots(
            interaction,
            JACKPOT_VALUE,
            interaction.guild.get_member(interaction.user.id),
        )

        STATE.state["trick_or_treat_jackpot_claimed"] = True

        message = self.JACKPOT_SUCCESS_PREFIX.format(
            mention=interaction.user.mention,
            ingot_icon=self.ingot_icon,
            amount=JACKPOT_VALUE,
        )
        embed = self._build_embed(
            message
            + self._get_balance_message(interaction.user.display_name, user_new_total or 0)
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
                message = self.REMOVE_ALL_TRICK_MESSAGE.format(
                    ingot_icon=self.ingot_icon, amount=member.ingots
                )
                embed = self._build_embed(
                    message + self._get_balance_message(interaction.user.display_name, 0)
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
        """Send a random Halloween-themed joke.

        Args:
            interaction: The Discord interaction context.
        """
        await interaction.followup.send(embed=self._build_embed(random.choice(self.JOKES)))

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
