import random
import re
import time
from typing import TYPE_CHECKING, Callable, Dict, Optional

import discord

from ironforgedbot.commands.holiday.trick_or_treat_constants import (
    QUIZ_CORRECT_MAX,
    QUIZ_CORRECT_MIN,
    QUIZ_PENALTY_CHANCE,
    QUIZ_WRONG_PENALTY_MAX,
    QUIZ_WRONG_PENALTY_MIN,
)
from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed

if TYPE_CHECKING:
    from ironforgedbot.commands.holiday.trick_or_treat_handler import (
        TrickOrTreatHandler,
    )

QUIZ_TIMEOUT_SECONDS = 35
DISCORD_BUTTON_LABEL_MAX_LENGTH = 80


def _format_with_emojis(text: str) -> str:
    """Replace emoji placeholders like {Ingot} with actual Discord emojis.

    Args:
        text: Text containing emoji placeholders in {EmojiName} format.

    Returns:
        Text with emoji placeholders replaced with actual emojis.
    """

    def replace_emoji(match: re.Match) -> str:
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
        super().__init__(timeout=float(QUIZ_TIMEOUT_SECONDS))
        self.handler = handler
        self.user_id = user_id
        self.question = question
        self.has_interacted = False
        self.message: Optional[discord.Message] = None

        for i in range(4):
            option = question["options"][i]
            text = option["text"]
            emoji_name = option.get("emoji")
            emoji = find_emoji(emoji_name) if emoji_name else None
            emoji = emoji or None

            button = discord.ui.Button(
                label=text[:DISCORD_BUTTON_LABEL_MAX_LENGTH],
                style=discord.ButtonStyle.primary,
                custom_id=f"quiz_master_option_{i}",
                emoji=emoji,
                row=0,
            )
            button.callback = self._create_answer_callback(i)
            self.add_item(button)

    def _create_answer_callback(
        self, option_index: int
    ) -> Callable[[discord.Interaction], None]:
        """Create a callback function for the given option index.

        Args:
            option_index: The index of the answer option (0-3).

        Returns:
            An async callback function for the button.
        """

        async def callback(interaction: discord.Interaction) -> None:
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

            await interaction.response.defer()
            if self.message:
                await self.message.delete()

            await process_quiz_answer(
                self.handler,
                interaction,
                option_index,
                self.question["correct_index"],
            )

            self.stop()

        return callback

    async def on_timeout(self):
        """Handle the view timing out."""
        if self.has_interacted or not self.message:
            return

        self.clear_items()

        user_nickname, ingot_total = await self.handler._get_user_info(self.user_id)

        message = self.handler.QUIZ_EXPIRED_MESSAGE
        if ingot_total is not None:
            message += self.handler._get_balance_message(user_nickname, ingot_total)

        embed = self.handler._build_embed(
            message,
            [
                "https://oldschool.runescape.wiki/images/thumb/Skull_%28item%29_detail.png/1024px-Skull_%28item%29_detail.png"
            ],
        )
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            pass


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

    original_question = random.choice(handler.QUIZ_QUESTIONS)

    correct_option = original_question["options"][original_question["correct_index"]]

    shuffled_options = original_question["options"].copy()
    random.shuffle(shuffled_options)

    new_correct_index = shuffled_options.index(correct_option)

    question = {
        "question": original_question["question"],
        "options": shuffled_options,
        "correct_index": new_correct_index,
    }

    formatted_question = _format_with_emojis(question["question"])

    expire_timestamp = int(time.time() + QUIZ_TIMEOUT_SECONDS)
    expires_formatted = f"<t:{expire_timestamp}:R>"

    intro_message = handler.QUIZ_INTRO.format(expires=expires_formatted)

    intro_embed = handler._build_embed(
        intro_message,
        ["https://oldschool.runescape.wiki/images/Quiz_Master.png"],
    )

    audience_confidence = random.randint(35, 90)
    question_text = f"### {formatted_question}"

    question_embed = build_response_embed(
        "Question",
        question_text,
        discord.Colour.blurple(),
    )
    question_embed.set_footer(
        text=f"contestant: {interaction.user.display_name}   •   audience confidence: {audience_confidence}%"
    )

    view = QuizMasterView(handler, interaction.user.id, question)
    message = await interaction.followup.send(
        embeds=[intro_embed, question_embed], view=view
    )
    view.message = message


async def _handle_correct_answer(
    handler: "TrickOrTreatHandler",
    interaction: discord.Interaction,
    user_nickname: str,
) -> Optional[str]:
    """Handle a correct quiz answer by awarding ingots.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
        user_nickname: The user's nickname for the response message.

    Returns:
        The formatted success message, or None if the user has no ingots.
    """
    assert interaction.guild

    amount = random.randrange(QUIZ_CORRECT_MIN, QUIZ_CORRECT_MAX, 1)
    ingot_total = await handler._adjust_ingots(
        interaction,
        amount,
        interaction.guild.get_member(interaction.user.id),
        reason="Trick or treat: quiz master correct answer",
    )

    if ingot_total is None:
        await interaction.followup.send(
            embed=handler._build_no_ingots_error_response(interaction.user.display_name)
        )
        return None

    message = handler.QUIZ_CORRECT_MESSAGE.format(
        ingot_icon=handler.ingot_icon, amount=amount
    )
    return message + handler._get_balance_message(user_nickname, ingot_total)


async def _handle_wrong_answer(
    handler: "TrickOrTreatHandler",
    interaction: discord.Interaction,
) -> str:
    """Handle a wrong quiz answer with potential penalty.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.

    Returns:
        The formatted response message.
    """
    assert interaction.guild

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
            # User has no ingots - lucky escape from penalty
            user_nickname, ingot_total = await handler._get_user_info(
                interaction.user.id
            )
            message = handler.QUIZ_WRONG_LUCKY_MESSAGE
            return message + handler._get_balance_message(user_nickname, ingot_total)

        user_nickname, _ = await handler._get_user_info(interaction.user.id)
        message = handler.QUIZ_WRONG_PENALTY_MESSAGE.format(
            ingot_icon=handler.ingot_icon,
            penalty=penalty,
        )
        return message + handler._get_balance_message(user_nickname, ingot_total)

    user_nickname, ingot_total = await handler._get_user_info(interaction.user.id)
    message = handler.QUIZ_WRONG_LUCKY_MESSAGE
    return message + handler._get_balance_message(user_nickname, ingot_total)


async def process_quiz_answer(
    handler: "TrickOrTreatHandler",
    interaction: discord.Interaction,
    chosen_index: int,
    correct_index: int,
) -> None:
    """Process the result of a quiz answer.

    If correct, award high amount of ingots.
    If incorrect, 50% chance to remove small amount of ingots.

    Args:
        handler: The TrickOrTreatHandler instance.
        interaction: The Discord interaction context.
        chosen_index: The index of the answer the user chose.
        correct_index: The index of the correct answer.
    """
    assert interaction.guild

    user_nickname, _ = await handler._get_user_info(interaction.user.id)

    thumbnail = "https://oldschool.runescape.wiki/images/thumb/Cabbage_detail.png/1280px-Cabbage_detail.png"
    if chosen_index == correct_index:
        message = await _handle_correct_answer(handler, interaction, user_nickname)
        thumbnail = "https://oldschool.runescape.wiki/images/Mystery_box_detail.png"
        if message is None:
            return
    else:
        message = await _handle_wrong_answer(handler, interaction)

    embed = handler._build_embed(message, [thumbnail])
    await interaction.followup.send(embed=embed)
