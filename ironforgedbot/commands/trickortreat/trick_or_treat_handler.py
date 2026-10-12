import json
import logging
import math
import random
from collections import deque
from typing import List, Optional, TypeVar

import discord

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import (
    BACKROOMS_BARGAIN_START_ROOM,
    BACKROOMS_DOOR_COUNT,
    BACKROOMS_MAX_ROOMS,
    CONTENT_FILE,
    TrickOrTreat,
)
from ironforgedbot.commands.trickortreat.types import (
    BackroomsData,
    BackroomsMessageCategory,
    ContentMessage,
    DoubleOrNothingData,
    GeneralData,
    HistoryDict,
    IngotAdjustment,
    IngotAdjustmentFailure,
    JackpotData,
    JokeData,
    QuizData,
    StealData,
    TrickData,
    TrickOrTreatContent,
    QUIZ_OPTION_COUNT,
)
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedcore.database import db
from ironforgedcore.services.ingot_service import IngotService
from ironforgedcore.services.member_service import MemberService

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TrickOrTreatHandler:
    """Handler for the trick-or-treat Halloween event minigame.

    Manages random outcomes that add or remove ingots from players,
    with various probabilities and reward/penalty amounts.
    """

    def __init__(self) -> None:
        """Initialize the TrickOrTreatHandler with message history and content."""
        self.ingot_icon: str = find_emoji("Ingot")

        self.history: HistoryDict = {
            "gif": deque(maxlen=150),
            "thumbnail": deque(maxlen=30),
            "backrooms_thumbnail": deque(maxlen=30),
            "backrooms_messages": {
                "intro": deque(maxlen=20),
                "continue_intro": deque(maxlen=20),
                "opening_door": deque(maxlen=20),
                "expired": deque(maxlen=20),
                "treasure": deque(maxlen=20),
                "fatal_monster": deque(maxlen=20),
                "monster": deque(maxlen=20),
                "escape": deque(maxlen=20),
                "bargain": deque(maxlen=20),
            },
            "positive_message": deque(maxlen=20),
            "negative_message": deque(maxlen=20),
            "quiz_question": deque(maxlen=20),
            "joke": deque(maxlen=20),
            "content_messages": {},
        }

        data = self._load_content_file()

        self.jackpot: JackpotData = data["jackpot"]
        self.double_or_nothing: DoubleOrNothingData = data["double_or_nothing"]
        self.steal: StealData = data["steal"]
        self.backrooms: BackroomsData = data["backrooms"]
        self.quiz: QuizData = data["quiz_master"]
        self.joke: JokeData = data["joke"]
        self.trick: TrickData = data["remove_all_trick"]

        self.gifs: List[str] = data["media"]["gifs"]
        self.thumbnails: List[str] = data["media"]["thumbnails"]
        self.general: GeneralData = data["general"]
        self.positive_messages: List[str] = self.general["positive_messages"]
        self.negative_messages: List[str] = self.general["negative_messages"]

    @staticmethod
    def _load_content_file(file_path: str = CONTENT_FILE) -> TrickOrTreatContent:
        """Load and parse the trick-or-treat content JSON file.

        Args:
            file_path: Path to the content JSON file. Defaults to CONTENT_FILE.

        Returns:
            Parsed JSON data as a dictionary.

        Raises:
            FileNotFoundError: If the content file doesn't exist.
            ValueError: If the JSON syntax is invalid.
            KeyError: If required keys are missing from the JSON.
            RuntimeError: For unexpected errors during loading.
        """
        try:
            with open(file_path) as f:
                logger.debug("Loading trick or treat data...")
                data = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Trick-or-treat content file not found: {e.filename}. "
                f"Expected file at: {file_path}"
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON syntax in trick-or-treat content file: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Unexpected error loading trick-or-treat content: {e}"
            ) from e

        if not isinstance(data, dict):
            raise ValueError(f"Content file must contain a JSON object: {file_path}")

        required_keys = [
            "jackpot",
            "double_or_nothing",
            "steal",
            "backrooms",
            "quiz_master",
            "joke",
            "remove_all_trick",
            "media",
            "general",
        ]
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise KeyError(
                f"Missing required keys in content file: {missing_keys}. "
                f"File: {file_path}"
            )

        TrickOrTreatHandler._validate_content_data(data, file_path)
        return data

    @staticmethod
    def _validate_content_data(data: dict, file_path: str) -> None:
        """Validate nested content required by outcome handlers."""
        section_fields = {
            "jackpot": ("success_prefix", "claimed_message"),
            "double_or_nothing": ("offer", "win", "lose", "keep", "expired"),
            "steal": (
                "offer",
                "success",
                "failure",
                "walk_away",
                "expired",
                "no_targets",
                "target_no_ingots",
                "user_no_ingots",
            ),
            "backrooms": (
                "intro_messages",
                "continue_intro_messages",
                "door_labels",
                "room_outcome_weights",
                "treasure_messages",
                "fatal_monster_messages",
                "monster_messages",
                "escape_messages",
                "bargain_messages",
                "opening_door_messages",
                "expired_messages",
                "thumbnails",
                "suspense_thumbnail",
            ),
            "quiz_master": (
                "intro",
                "questions",
                "correct_message",
                "wrong_lucky_message",
                "wrong_penalty_message",
                "expired_message",
            ),
            "joke": ("messages",),
            "remove_all_trick": ("message",),
            "media": ("gifs", "thumbnails"),
            "general": ("positive_messages", "negative_messages", "no_ingots_message"),
        }
        list_fields = {
            ("backrooms", "door_labels"),
            ("backrooms", "intro_messages"),
            ("backrooms", "continue_intro_messages"),
            ("backrooms", "treasure_messages"),
            ("backrooms", "fatal_monster_messages"),
            ("backrooms", "monster_messages"),
            ("backrooms", "escape_messages"),
            ("backrooms", "bargain_messages"),
            ("backrooms", "opening_door_messages"),
            ("backrooms", "expired_messages"),
            ("backrooms", "thumbnails"),
            ("quiz_master", "questions"),
            ("joke", "messages"),
            ("media", "gifs"),
            ("media", "thumbnails"),
            ("general", "positive_messages"),
            ("general", "negative_messages"),
        }
        message_fields = {
            ("jackpot", "success_prefix"),
            ("jackpot", "claimed_message"),
            ("double_or_nothing", "offer"),
            ("double_or_nothing", "win"),
            ("double_or_nothing", "lose"),
            ("double_or_nothing", "keep"),
            ("double_or_nothing", "expired"),
            ("steal", "offer"),
            ("steal", "success"),
            ("steal", "failure"),
            ("steal", "walk_away"),
            ("steal", "expired"),
            ("steal", "no_targets"),
            ("steal", "target_no_ingots"),
            ("steal", "user_no_ingots"),
            ("quiz_master", "intro"),
            ("quiz_master", "correct_message"),
            ("quiz_master", "wrong_lucky_message"),
            ("quiz_master", "wrong_penalty_message"),
            ("quiz_master", "expired_message"),
            ("remove_all_trick", "message"),
            ("general", "no_ingots_message"),
        }

        for section, fields in section_fields.items():
            section_data = data[section]
            if not isinstance(section_data, dict):
                raise ValueError(
                    f"Content section '{section}' must be an object in {file_path}"
                )

            missing_fields = [field for field in fields if field not in section_data]
            if missing_fields:
                raise KeyError(
                    f"Missing fields in content section '{section}': "
                    f"{missing_fields}. File: {file_path}"
                )

            for field in fields:
                value = section_data[field]
                if (section, field) in list_fields:
                    if not isinstance(value, list) or not value:
                        raise ValueError(
                            f"Content field '{section}.{field}' must be a non-empty "
                            f"list in {file_path}"
                        )
                    if (section, field) != ("quiz_master", "questions") and any(
                        not isinstance(item, str) or not item.strip() for item in value
                    ):
                        raise ValueError(
                            f"Content field '{section}.{field}' must contain "
                            f"non-empty strings in {file_path}"
                        )
                elif (section, field) in message_fields:
                    messages = value if isinstance(value, list) else [value]
                    if not messages or any(
                        not isinstance(message, str) or not message.strip()
                        for message in messages
                    ):
                        raise ValueError(
                            f"Content field '{section}.{field}' must contain a "
                            f"non-empty message string or list in {file_path}"
                        )
                elif (section, field) == ("backrooms", "room_outcome_weights"):
                    if not isinstance(value, dict):
                        raise ValueError(
                            "Content field 'backrooms.room_outcome_weights' must be "
                            f"an object in {file_path}"
                        )
                elif not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Content field '{section}.{field}' must be a non-empty "
                        f"string in {file_path}"
                    )

        room_outcome_weights = data["backrooms"]["room_outcome_weights"]
        expected_room_keys = {
            str(room_number) for room_number in range(1, BACKROOMS_MAX_ROOMS + 1)
        }
        actual_room_keys = set(room_outcome_weights)
        missing_rooms = expected_room_keys - actual_room_keys
        unknown_rooms = actual_room_keys - expected_room_keys
        if missing_rooms or unknown_rooms:
            raise ValueError(
                "Content field 'backrooms.room_outcome_weights' must define rooms "
                f"{sorted(expected_room_keys)}; missing {sorted(missing_rooms)}, "
                f"unknown {sorted(unknown_rooms)}"
            )

        if room_outcome_weights["1"] != {"treasure": 1.0}:
            raise ValueError(
                "Content field 'backrooms.room_outcome_weights.1' must guarantee "
                "treasure in the first room"
            )

        valid_outcomes = {
            "treasure",
            "fatal_monster",
            "escapable_monster",
            "escape",
            "bargain",
        }
        for room_number, weights in room_outcome_weights.items():
            if not isinstance(weights, dict) or not weights:
                raise ValueError(
                    "Content field 'backrooms.room_outcome_weights."
                    f"{room_number}' must be a non-empty object"
                )

            unknown_outcomes = set(weights) - valid_outcomes
            if unknown_outcomes:
                raise ValueError(
                    "Content field 'backrooms.room_outcome_weights."
                    f"{room_number}' has unknown outcomes: {sorted(unknown_outcomes)}"
                )

            if "bargain" in weights:
                if int(room_number) < BACKROOMS_BARGAIN_START_ROOM:
                    raise ValueError(
                        "Content field 'backrooms.room_outcome_weights."
                        f"{room_number}' has bargain before room "
                        f"{BACKROOMS_BARGAIN_START_ROOM}"
                    )
                if not {"treasure", "escape"}.issubset(weights):
                    raise ValueError(
                        "Content field 'backrooms.room_outcome_weights."
                        f"{room_number}' bargain weights require treasure and escape"
                    )

            for outcome, weight in weights.items():
                if (
                    isinstance(weight, bool)
                    or not isinstance(weight, (int, float))
                    or not 0 <= weight <= 1
                    or (isinstance(weight, float) and not math.isfinite(weight))
                ):
                    raise ValueError(
                        "Content field 'backrooms.room_outcome_weights."
                        f"{room_number}.{outcome}' must be a finite probability "
                        "between 0 and 1"
                    )

            if not math.isclose(sum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-9):
                raise ValueError(
                    "Content field 'backrooms.room_outcome_weights."
                    f"{room_number}' weights must sum to 1"
                )

        for index, question in enumerate(data["quiz_master"]["questions"]):
            if not isinstance(question, dict):
                raise ValueError(f"Quiz question {index} must be an object")

            question_text = question.get("question")
            if not isinstance(question_text, str) or not question_text.strip():
                raise ValueError(f"Quiz question {index} needs non-empty question text")

            options = question.get("options")
            if not isinstance(options, list) or len(options) != QUIZ_OPTION_COUNT:
                raise ValueError(
                    f"Quiz question {index} must have exactly {QUIZ_OPTION_COUNT} options"
                )

            correct_index = question.get("correct_index")
            if type(correct_index) is not int or not 0 <= correct_index < len(options):
                raise ValueError(f"Quiz question {index} has invalid correct_index")

            if any(
                not isinstance(option, dict)
                or not isinstance(option.get("text"), str)
                or not option["text"].strip()
                for option in options
            ):
                raise ValueError(f"Quiz question {index} options need non-empty text")

        door_labels = data["backrooms"]["door_labels"]
        if len(door_labels) < BACKROOMS_DOOR_COUNT:
            raise ValueError(
                "Backrooms needs at least "
                f"{BACKROOMS_DOOR_COUNT} door labels in {file_path}"
            )

    def _get_random_from_list(self, items: List[T], history: deque[int]) -> T:
        """Get a random item from a list, avoiding recently used items.

        Args:
            items: The full list of items to choose from.
            history: Index-based deque tracking recently used item indices.

        Returns:
            A randomly chosen item that hasn't been used recently.
        """
        if not items:
            raise ValueError("items must be a non-empty list")

        available_indices = [i for i in range(len(items)) if i not in history]

        if not available_indices:
            history.clear()
            available_indices = list(range(len(items)))

        chosen_idx = random.choice(available_indices)
        history.append(chosen_idx)
        return items[chosen_idx]

    def _get_backrooms_message(
        self, category: BackroomsMessageCategory, messages: list[str]
    ) -> str:
        return self._get_random_from_list(
            messages, self.history["backrooms_messages"][category]
        )

    def _get_content_message(self, key: str, messages: ContentMessage) -> str:
        if isinstance(messages, str):
            return messages

        history = self.history["content_messages"].setdefault(key, deque(maxlen=20))
        return self._get_random_from_list(messages, history)

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
                              If None, uses self.history["thumbnail"].

        Returns:
            A Discord embed with orange color and random thumbnail.
        """
        thumbnails = thumbnail_list if thumbnail_list is not None else self.thumbnails
        history = (
            thumbnail_history
            if thumbnail_history is not None
            else self.history["thumbnail"]
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
            self._get_content_message(
                "general.no_ingots_message", self.general["no_ingots_message"]
            )
            + self._get_balance_message(username, 0)
        )

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
    ) -> IngotAdjustment:
        """Adjust balance and report resulting total and applied quantity.

        Args:
            interaction: The Discord interaction context.
            quantity: Number of ingots to add (positive) or remove (negative).
            discord_member: The Discord member to adjust ingots for.
            reason: Optional changelog reason. Defaults to "Trick or treat win/loss".

        Returns:
            Adjustment totals and failure category, when adjustment fails.
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
                    return IngotAdjustment(None, 0, IngotAdjustmentFailure.ERROR)

                if member.ingots == 0:
                    # User has no ingots to lose
                    return IngotAdjustment(None, 0, IngotAdjustmentFailure.NO_INGOTS)

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
                return IngotAdjustment(None, 0, IngotAdjustmentFailure.ERROR)

            if not result.status:
                await send_error_response(interaction, result.message)
                return IngotAdjustment(None, 0, IngotAdjustmentFailure.ERROR)

            return IngotAdjustment(result.new_total, quantity)

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

        adjustment = await self._adjust_ingots(
            interaction,
            quantity,
            interaction.guild.get_member(interaction.user.id),
            reason=reason,
        )

        if adjustment.failure is IngotAdjustmentFailure.ERROR:
            return

        # Get member nickname from database
        async with db.get_session() as session:
            member_service = MemberService(session)
            user_member = await member_service.get_member_by_discord_id(
                interaction.user.id
            )
            user_nickname = user_member.nickname if user_member else "User"

        if adjustment.failure is IngotAdjustmentFailure.NO_INGOTS:
            await interaction.followup.send(
                embed=self._build_no_ingots_error_response(user_nickname)
            )
            return

        assert adjustment.new_total is not None
        ingot_total = adjustment.new_total
        actual_quantity = adjustment.applied_quantity

        if is_positive:
            message_text = self._get_random_from_list(
                self.positive_messages, self.history["positive_message"]
            )
        else:
            message_text = self._get_random_from_list(
                self.negative_messages, self.history["negative_message"]
            )

        prefix = "**🎃 Treat!**\n\n" if is_positive else "**💀 Trick!**\n\n"
        formatted_quantity = (
            f"-{abs(actual_quantity):,}"
            if actual_quantity < 0
            else f"{actual_quantity:,}"
        )
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

        # return await backrooms.result_backrooms(self, interaction)

        match random.choices(
            list(TrickOrTreat), weights=[item.value for item in TrickOrTreat]
        )[0]:
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
