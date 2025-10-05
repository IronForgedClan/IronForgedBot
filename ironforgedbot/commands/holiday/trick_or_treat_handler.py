"""Handler for the trick-or-treat Halloween event minigame."""

import json
import logging
import random
from typing import List, Optional

import discord

from ironforgedbot.commands.holiday.trick_or_treat_constants import (
    NEGATIVE_MESSAGE_HISTORY_LIMIT,
    POSITIVE_MESSAGE_HISTORY_LIMIT,
    THUMBNAIL_HISTORY_LIMIT,
    TrickOrTreat,
)
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.database.database import db
from ironforgedbot.services.ingot_service import IngotService
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


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
        self.DOUBLE_OR_NOTHING_OFFER: str
        self.DOUBLE_OR_NOTHING_WIN: str
        self.DOUBLE_OR_NOTHING_LOSE: str
        self.DOUBLE_OR_NOTHING_KEEP: str
        self.DOUBLE_OR_NOTHING_EXPIRED: str
        self.STEAL_OFFER: str
        self.STEAL_SUCCESS: str
        self.STEAL_FAILURE: str
        self.STEAL_WALK_AWAY: str
        self.STEAL_EXPIRED: str
        self.STEAL_NO_TARGETS: str
        self.STEAL_TARGET_NO_INGOTS: str
        self.STEAL_USER_NO_INGOTS: str
        self.HAUNTED_HOUSE_INTRO: str
        self.HAUNTED_HOUSE_DOOR_LABELS: list[str]
        self.HAUNTED_HOUSE_TREASURE_MESSAGES: list[str]
        self.HAUNTED_HOUSE_MONSTER_MESSAGES: list[str]
        self.HAUNTED_HOUSE_ESCAPE_MESSAGES: list[str]
        self.HAUNTED_HOUSE_EXPIRED_MESSAGE: str

        with open("data/trick_or_treat.json") as f:
            logger.debug("Loading trick or treat data...")
            data = json.load(f)

            self.GIFS = data["MEDIA"]["GIFS"]
            self.THUMBNAILS = data["MEDIA"]["THUMBNAILS"]
            self.POSITIVE_MESSAGES = data["GENERAL"]["POSITIVE_MESSAGES"]
            self.NEGATIVE_MESSAGES = data["GENERAL"]["NEGATIVE_MESSAGES"]
            self.NEGATIVE_ANNOYANCES = data["GENERAL"]["NEGATIVE_ANNOYANCES"]
            self.JOKES = data["JOKE"]["MESSAGES"]
            self.NO_INGOTS_MESSAGE = data["GENERAL"]["NO_INGOTS_MESSAGE"]
            self.JACKPOT_SUCCESS_PREFIX = data["JACKPOT"]["SUCCESS_PREFIX"]
            self.JACKPOT_CLAIMED_MESSAGE = data["JACKPOT"]["CLAIMED_MESSAGE"]
            self.REMOVE_ALL_TRICK_MESSAGE = data["REMOVE_ALL_TRICK"]["MESSAGE"]
            self.DOUBLE_OR_NOTHING_OFFER = data["DOUBLE_OR_NOTHING"]["OFFER"]
            self.DOUBLE_OR_NOTHING_WIN = data["DOUBLE_OR_NOTHING"]["WIN"]
            self.DOUBLE_OR_NOTHING_LOSE = data["DOUBLE_OR_NOTHING"]["LOSE"]
            self.DOUBLE_OR_NOTHING_KEEP = data["DOUBLE_OR_NOTHING"]["KEEP"]
            self.DOUBLE_OR_NOTHING_EXPIRED = data["DOUBLE_OR_NOTHING"]["EXPIRED"]
            self.STEAL_OFFER = data["STEAL"]["OFFER"]
            self.STEAL_SUCCESS = data["STEAL"]["SUCCESS"]
            self.STEAL_FAILURE = data["STEAL"]["FAILURE"]
            self.STEAL_WALK_AWAY = data["STEAL"]["WALK_AWAY"]
            self.STEAL_EXPIRED = data["STEAL"]["EXPIRED"]
            self.STEAL_NO_TARGETS = data["STEAL"]["NO_TARGETS"]
            self.STEAL_TARGET_NO_INGOTS = data["STEAL"]["TARGET_NO_INGOTS"]
            self.STEAL_USER_NO_INGOTS = data["STEAL"]["USER_NO_INGOTS"]
            self.HAUNTED_HOUSE_INTRO = data["HAUNTED_HOUSE"]["INTRO"]
            self.HAUNTED_HOUSE_DOOR_LABELS = data["HAUNTED_HOUSE"]["DOOR_LABELS"]
            self.HAUNTED_HOUSE_TREASURE_MESSAGES = data["HAUNTED_HOUSE"][
                "TREASURE_MESSAGES"
            ]
            self.HAUNTED_HOUSE_MONSTER_MESSAGES = data["HAUNTED_HOUSE"][
                "MONSTER_MESSAGES"
            ]
            self.HAUNTED_HOUSE_ESCAPE_MESSAGES = data["HAUNTED_HOUSE"][
                "ESCAPE_MESSAGES"
            ]
            self.HAUNTED_HOUSE_EXPIRED_MESSAGE = data["HAUNTED_HOUSE"]["EXPIRED"]

    def _get_random_positive_message(self) -> str:
        """Get a random positive message for when player wins ingots.

        Returns:
            A message template string with {ingots} placeholder.
        """
        chosen = random.choice(
            [
                s
                for s in self.POSITIVE_MESSAGES
                if s not in self.positive_message_history
            ]
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
        chosen = random.choice(
            [
                s
                for s in self.NEGATIVE_MESSAGES
                if s not in self.negative_message_history
            ]
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
        reason: Optional[str] = None,
    ) -> Optional[int]:
        """Add or remove ingots from a player's account.

        Args:
            interaction: The Discord interaction context.
            quantity: Number of ingots to add (positive) or remove (negative).
            discord_member: The Discord member to adjust ingots for.
            reason: Optional changelog reason. Defaults to "Trick or treat win/loss".

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
                changelog_reason = reason or "Trick or treat: win"
                result = await ingot_service.try_add_ingots(
                    discord_member.id, quantity, None, changelog_reason
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

                changelog_reason = reason or "Trick or treat: loss"
                result = await ingot_service.try_remove_ingots(
                    discord_member.id, quantity, None, changelog_reason
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

        # Determine reason based on outcome type
        if is_positive:
            reason = "Trick or treat: win"
        else:
            reason = "Trick or treat: loss"

        ingot_total = await self._adjust_ingots(
            interaction,
            quantity,
            interaction.guild.get_member(interaction.user.id),
            reason=reason,
        )

        # Get member nickname from database
        async with db.get_session() as session:
            member_service = MemberService(session)
            user_member = await member_service.get_member_by_discord_id(
                interaction.user.id
            )
            user_nickname = user_member.nickname if user_member else "User"

        if ingot_total is None:
            await interaction.followup.send(
                embed=self._build_no_ingots_error_response(user_nickname)
            )
            return

        message_getter = (
            self._get_random_positive_message
            if is_positive
            else self._get_random_negative_message
        )

        prefix = "**🎃 Treat!**\n\n" if is_positive else "**💀 Trick!**\n\n"
        formatted_quantity = f"-{abs(quantity):,}" if quantity < 0 else f"{quantity:,}"
        message = message_getter().format(
            ingots=f"{self.ingot_icon}{formatted_quantity}"
        )

        embed = self._build_embed(
            prefix + message + self._get_balance_message(user_nickname, ingot_total)
        )
        await interaction.followup.send(embed=embed)

    async def random_result(self, interaction: discord.Interaction) -> None:
        """Randomly select and execute a trick-or-treat outcome.

        Args:
            interaction: The Discord interaction context.
        """
        # Import outcome modules here to avoid circular imports
        from ironforgedbot.commands.holiday.outcomes import (
            double_or_nothing,
            gif,
            haunted_house,
            ingot_changes,
            jackpot,
            joke,
            steal,
            trick,
        )

        match random.choices(list(TrickOrTreat), weights=self.weights)[0]:
            case TrickOrTreat.JACKPOT_INGOTS:
                return await jackpot.result_jackpot(self, interaction)
            case TrickOrTreat.REMOVE_ALL_INGOTS_TRICK:
                return await trick.result_remove_all_ingots_trick(self, interaction)
            case TrickOrTreat.DOUBLE_OR_NOTHING:
                return await double_or_nothing.result_double_or_nothing(
                    self, interaction
                )
            case TrickOrTreat.STEAL:
                return await steal.result_steal(self, interaction)
            case TrickOrTreat.HAUNTED_HOUSE:
                return await haunted_house.result_haunted_house(self, interaction)
            case TrickOrTreat.REMOVE_INGOTS_HIGH:
                return await ingot_changes.result_remove_high(self, interaction)
            case TrickOrTreat.ADD_INGOTS_HIGH:
                return await ingot_changes.result_add_high(self, interaction)
            case TrickOrTreat.REMOVE_INGOTS_LOW:
                return await ingot_changes.result_remove_low(self, interaction)
            case TrickOrTreat.ADD_INGOTS_LOW:
                return await ingot_changes.result_add_low(self, interaction)
            case TrickOrTreat.JOKE:
                return await joke.result_joke(self, interaction)
            case TrickOrTreat.GIF:
                return await gif.result_gif(self, interaction)


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
