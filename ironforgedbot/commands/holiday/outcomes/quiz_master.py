"""Quiz Master outcome for trick-or-treat."""

import random
import re
import time
from typing import TYPE_CHECKING, Dict, Optional

import discord

from ironforgedbot.commands.holiday.trick_or_treat_constants import (
    QUIZ_CORRECT_MAX,
    QUIZ_CORRECT_MIN,
    QUIZ_PENALTY_CHANCE,
    QUIZ_WRONG_PENALTY_MAX,
    QUIZ_WRONG_PENALTY_MIN,
)
from ironforgedbot.common.helpers import find_emoji

if TYPE_CHECKING:
    from ironforgedbot.commands.holiday.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )


def _format_with_emojis(text: str) -> str:
    """Replace emoji placeholders like {Ingot} with actual Discord emojis.

    Args:
        text: Text containing emoji placeholders in {EmojiName} format.

    Returns:
        Text with emoji placeholders replaced with actual emojis.
    """

    def replace_emoji(match):
        emoji_name = match.group(1)
        emoji = find_emoji(emoji_name)
        return emoji if emoji else match.group(0)

    return re.sub(r"\{(\w+)\}", replace_emoji, text)


class QuizMasterView(discord.ui.View):
    """Discord UI View for the quiz master button interaction.

    Displays 4 buttons representing multiple choice answers.
    The view times out after 30 seconds.
    """

    def __init__(
        self,
        handler: "TrickOrTreatHandler",
        user_id: int,
        question: Dict,
    ):
        """Initialize the quiz master view.

        Args:
            handler: The TrickOrTreatHandler instance to use for processing the result.
            user_id: The Discord user ID who can interact with this button.
            question: The question dictionary containing question, options, and correct_index.
        """
        super().__init__(timeout=30.0)
        self.handler = handler
        self.user_id = user_id
        self.question = question
        self.has_interacted = False
        self.message: Optional[discord.Message] = None

        # Create 4 buttons for the answer options
        button_labels = ["A", "B", "C", "D"]

        for i in range(4):
            option = question["options"][i]
            # Handle both dict format {"text": "...", "emoji": "..."} and legacy string format
            if isinstance(option, dict):
                text = option["text"]
                emoji_name = option.get("emoji")
                emoji = find_emoji(emoji_name) if emoji_name else None
            else:
                text = option
                emoji = None

            button = discord.ui.Button(
                label=f"{button_labels[i]}: {text}"[:80],  # Discord limit
                style=discord.ButtonStyle.primary,
                custom_id=f"quiz_master_option_{i}",
                emoji=emoji,
                row=0,  # All buttons on one row
            )
            button.callback = self._create_answer_callback(i)
            self.add_item(button)

    def _create_answer_callback(self, option_index: int):
        """Create a callback function for the given option index.

        Args:
            option_index: The index of the answer option (0-3).

        Returns:
            An async callback function for the button.
        """

        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "This isn't your quiz!", ephemeral=True
                )
                return

            if self.has_interacted:
                await interaction.response.send_message(
                    "You already answered!", ephemeral=True
                )
                return

            self.has_interacted = True

            # Delete the original message
            await interaction.response.defer()
            if self.message:
                await self.message.delete()

            # Get correct answer text
            correct_option = self.question["options"][self.question["correct_index"]]
            correct_answer = (
                correct_option["text"]
                if isinstance(correct_option, dict)
                else correct_option
            )

            await process_quiz_answer(
                self.handler,
                interaction,
                option_index,
                self.question["correct_index"],
                correct_answer,
            )

            self.stop()

        return callback

    async def on_timeout(self):
        """Handle the view timing out after 30 seconds."""
        if self.has_interacted or not self.message:
            return

        # Remove all buttons
        self.clear_items()

        # Get current ingot total and nickname from database
        from ironforgedbot.database.database import db
        from ironforgedbot.services.member_service import MemberService

        ingot_total = None
        user_nickname = "User"

        async with db.get_session() as session:
            member_service = MemberService(session)
            user_member = await member_service.get_member_by_discord_id(self.user_id)
            if user_member:
                ingot_total = user_member.ingots
                user_nickname = user_member.nickname

        # Format the expired message
        correct_option = self.question["options"][self.question["correct_index"]]
        correct_answer = (
            correct_option["text"] if isinstance(correct_option, dict) else correct_option
        )
        message = self.handler.QUIZ_EXPIRED_MESSAGE.format(
            correct_answer=correct_answer
        )
        if ingot_total is not None:
            message += self.handler._get_balance_message(user_nickname, ingot_total)

        embed = self.handler._build_embed(message)
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass  # Message may have been deleted


async def result_quiz_master(
    handler: "TrickOrTreatHandler", interaction: discord.Interaction
) -> None:
    """Present the player with a quiz question.

    If answered correctly, awards high amount of ingots.
    If answered incorrectly, 50% chance to take a small amount of ingots.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
    """
    assert interaction.guild

    # Select a random question
    question = random.choice(handler.QUIZ_QUESTIONS)

    # Format question with emojis
    formatted_question = _format_with_emojis(question["question"])

    # Calculate expiration timestamp and format as Discord countdown
    expire_timestamp = int(time.time() + 30)
    expires_formatted = f"<t:{expire_timestamp}:R>"

    # Create the intro message
    intro_message = handler.QUIZ_INTRO.format(expires=expires_formatted)
    intro_message += f"\n\n**{formatted_question}**"

    embed = handler._build_embed(intro_message)

    # Create and send the view with the buttons
    view = QuizMasterView(handler, interaction.user.id, question)
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message


async def process_quiz_answer(
    handler: "TrickOrTreatHandler",
    interaction: discord.Interaction,
    chosen_index: int,
    correct_index: int,
    correct_answer: str,
) -> None:
    """Process the result of a quiz answer.

    If correct, award high amount of ingots.
    If incorrect, 50% chance to remove small amount of ingots.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
        chosen_index: The index of the answer the user chose.
        correct_index: The index of the correct answer.
        correct_answer: The text of the correct answer (already formatted).
    """
    assert interaction.guild

    # Get member nickname from database
    from ironforgedbot.database.database import db
    from ironforgedbot.services.member_service import MemberService

    async with db.get_session() as session:
        member_service = MemberService(session)
        user_member = await member_service.get_member_by_discord_id(interaction.user.id)
        user_nickname = user_member.nickname if user_member else "User"

    if chosen_index == correct_index:
        # Correct answer - award high ingots
        amount = random.randrange(QUIZ_CORRECT_MIN, QUIZ_CORRECT_MAX, 1)
        ingot_total = await handler._adjust_ingots(
            interaction,
            amount,
            interaction.guild.get_member(interaction.user.id),
            reason="Trick or treat: quiz master correct answer",
        )

        if ingot_total is None:
            await interaction.followup.send(
                embed=handler._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )
            return

        message = handler.QUIZ_CORRECT_MESSAGE.format(
            ingot_icon=handler.ingot_icon, amount=amount
        )
        message += handler._get_balance_message(user_nickname, ingot_total)
    else:
        # Wrong answer - 50% chance to take small amount
        take_penalty = random.random() < QUIZ_PENALTY_CHANCE

        if take_penalty:
            penalty = random.randrange(QUIZ_WRONG_PENALTY_MIN, QUIZ_WRONG_PENALTY_MAX, 1)
            ingot_total = await handler._adjust_ingots(
                interaction,
                -penalty,
                interaction.guild.get_member(interaction.user.id),
                reason="Trick or treat: quiz master wrong answer penalty",
            )

            if ingot_total is None:
                # User has no ingots - lucky escape
                async with db.get_session() as session:
                    member_service = MemberService(session)
                    user_member = await member_service.get_member_by_discord_id(
                        interaction.user.id
                    )
                    ingot_total = 0
                    user_nickname = user_member.nickname if user_member else "User"

                message = handler.QUIZ_WRONG_LUCKY_MESSAGE.format(
                    correct_answer=correct_answer
                )
                message += handler._get_balance_message(user_nickname, ingot_total)
            else:
                message = handler.QUIZ_WRONG_PENALTY_MESSAGE.format(
                    correct_answer=correct_answer,
                    ingot_icon=handler.ingot_icon,
                    penalty=penalty,
                )
                message += handler._get_balance_message(user_nickname, ingot_total)
        else:
            # Wrong but no penalty
            async with db.get_session() as session:
                member_service = MemberService(session)
                user_member = await member_service.get_member_by_discord_id(
                    interaction.user.id
                )
                ingot_total = user_member.ingots if user_member else 0
                user_nickname = user_member.nickname if user_member else "User"

            message = handler.QUIZ_WRONG_LUCKY_MESSAGE.format(
                correct_answer=correct_answer
            )
            message += handler._get_balance_message(user_nickname, ingot_total)

    embed = handler._build_embed(message)
    await interaction.followup.send(embed=embed)
