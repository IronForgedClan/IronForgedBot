import json
import logging
import random
from collections import deque
from typing import List, Optional, TypeVar

import discord

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    CONTENT_FILE,
    TrickOrTreat,
)
from ironforgedbot.commands.trickortreat.types import (
    BackroomsData,
    DoubleOrNothingData,
    GeneralData,
    JackpotData,
    JokeData,
    QuizData,
    StealData,
    TrickData,
)
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.database.database import db
from ironforgedbot.services.ingot_service import IngotService
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TrickOrTreatHandler:
    """Handler for the trick-or-treat Halloween event minigame.

    Manages random outcomes that add or remove ingots from players,
    with various probabilities and reward/penalty amounts.
    """

    def __init__(self) -> None:
        """Initialize the TrickOrTreatHandler with weighted outcomes and message history."""
        self.weights: List[float] = [item.value for item in TrickOrTreat]
        self.ingot_icon: str = find_emoji("Ingot")

        # History tracking
        self.gif_history: deque[int] = deque(maxlen=150)
        self.thumbnail_history: deque[int] = deque(maxlen=30)
        self.backrooms_thumbnail_history: deque[int] = deque(maxlen=30)
        self.positive_message_history: deque[int] = deque(maxlen=20)
        self.negative_message_history: deque[int] = deque(maxlen=20)
        self.quiz_question_history: deque[int] = deque(maxlen=20)
        self.joke_history: deque[int] = deque(maxlen=20)

        # Load content
        with open(CONTENT_FILE) as f:
            logger.debug("Loading trick or treat data...")
            data = json.load(f)

        # Outcome data
        self.general: GeneralData = data["GENERAL"]
        self.jackpot: JackpotData = data["JACKPOT"]
        self.double_or_nothing: DoubleOrNothingData = data["DOUBLE_OR_NOTHING"]
        self.steal: StealData = data["STEAL"]
        self.backrooms: BackroomsData = data["BACKROOMS"]
        self.quiz: QuizData = data["QUIZ_MASTER"]
        self.joke: JokeData = data["JOKE"]
        self.trick: TrickData = data["REMOVE_ALL_TRICK"]

        # Common lists
        self.gifs: List[str] = data["MEDIA"]["GIFS"]
        self.thumbnails: List[str] = data["MEDIA"]["THUMBNAILS"]
        self.positive_messages: List[str] = self.general["POSITIVE_MESSAGES"]
        self.negative_messages: List[str] = self.general["NEGATIVE_MESSAGES"]

    def _get_random_from_list(self, items: List[T], history: deque[int]) -> T:
        """Get a random item from a list, avoiding recently used items.

        Args:
            items: The full list of items to choose from.
            history: Index-based deque tracking recently used item indices.

        Returns:
            A randomly chosen item that hasn't been used recently.
        """
        available_indices = [i for i in range(len(items)) if i not in history]

        if not available_indices:
            history.clear()
            available_indices = list(range(len(items)))

        chosen_idx = random.choice(available_indices)
        history.append(chosen_idx)
        return items[chosen_idx]

    def _get_balance_message(self, username: str, balance: int) -> str:
        """Generate a formatted message showing the user's new ingot balance.

        Args:
            username: The player's display name.
            balance: The new ingot balance.

        Returns:
            A formatted string showing the new balance.
        """
        return f"\n\n**{username}** now has **{self.ingot_icon}{balance:,}** ingots."

    def _build_embed(
        self,
        content: str,
        thumbnail_list: Optional[List[str]] = None,
        thumbnail_history: Optional[deque[int]] = None,
    ) -> discord.Embed:
        """Build a Discord embed with Halloween-themed styling.

        Args:
            content: The message content to display in the embed.
            thumbnail_list: Optional list of thumbnails to choose from.
                           If None, uses default THUMBNAILS.
            thumbnail_history: Optional index-based history for thumbnail selection.
                              If None, uses self.thumbnail_history.

        Returns:
            A Discord embed with orange color and random thumbnail.
        """
        thumbnails = thumbnail_list if thumbnail_list is not None else self.thumbnails
        history = (
            thumbnail_history
            if thumbnail_history is not None
            else self.thumbnail_history
        )

        if len(thumbnails) == 1:
            chosen_thumbnail = thumbnails[0]
        else:
            chosen_thumbnail = self._get_random_from_list(thumbnails, history)

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
            self.general["NO_INGOTS_MESSAGE"] + self._get_balance_message(username, 0)
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

    async def _get_user_info(self, user_id: int) -> tuple[str, int]:
        """Get user nickname and ingot total from database.

        Args:
            user_id: Discord user ID.

        Returns:
            Tuple of (nickname, ingot_total). Uses defaults if user not found.
        """
        async with db.get_session() as session:
            member_service = MemberService(session)
            user_member = await member_service.get_member_by_discord_id(user_id)
            if user_member:
                return user_member.nickname, user_member.ingots
            return "User", 0

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

        if is_positive:
            message_text = self._get_random_from_list(
                self.positive_messages, self.positive_message_history
            )
        else:
            message_text = self._get_random_from_list(
                self.negative_messages, self.negative_message_history
            )

        prefix = "**🎃 Treat!**\n\n" if is_positive else "**💀 Trick!**\n\n"
        formatted_quantity = f"-{abs(quantity):,}" if quantity < 0 else f"{quantity:,}"
        message = message_text.format(ingots=f"{self.ingot_icon}{formatted_quantity}")

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
        from ironforgedbot.commands.trickortreat.outcomes import (
            backrooms,
            double_or_nothing,
            gif,
            ingot_changes,
            jackpot,
            joke,
            quiz_master,
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
            case TrickOrTreat.QUIZ_MASTER:
                return await quiz_master.result_quiz_master(self, interaction)
            case TrickOrTreat.BACKROOMS:
                return await backrooms.result_backrooms(self, interaction)
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
