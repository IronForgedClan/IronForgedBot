import logging

import discord

from ironforgedbot.commands.spin.build_spin_gif import build_spin_gif_file
from ironforgedbot.commands.spin.spin_result_handler import send_spin_result
from ironforgedcore.common.normalize import normalize_discord_string
from ironforgedbot.common.responses import send_error_response

logger = logging.getLogger(__name__)


class SpinMembersView(discord.ui.View):
    """Ephemeral view with a RoleSelect dropdown to pick members for spin."""

    def __init__(self) -> None:
        super().__init__(timeout=120)
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.delete()
        return await super().on_timeout()

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select a role to spin members from...",
        min_values=1,
        max_values=1,
    )
    async def role_select(
        self, interaction: discord.Interaction, select: discord.ui.RoleSelect
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        role = select.values[0]

        member_name_pairs: list[tuple[str, discord.Member]] = []
        for member in role.members:
            if member.bot:
                continue
            display_name = normalize_discord_string(member.display_name)
            if display_name:
                member_name_pairs.append((display_name, member))
        display_names = [name for name, _ in member_name_pairs]

        if not display_names:
            await send_error_response(
                interaction,
                f"The role **{role.name}** has no eligible members to spin.",
            )
            return

        try:
            file, winner_display_name = await build_spin_gif_file(display_names)
        except Exception as e:
            logger.error(f"Error generating spin GIF: {e}")
            await send_error_response(
                interaction,
                "Failed to generate spin animation. Please try again later.",
            )
            return

        winning_member = next(
            (m for name, m in member_name_pairs if name == winner_display_name),
            None,
        )
        winner_mention = (
            winning_member.mention if winning_member else winner_display_name
        )

        if self.message:
            await self.message.delete()
            self.message = None

        await send_spin_result(
            interaction,
            file,
            winner_mention,
            spinning_text=f"_spinning everyone with the **{role.name}** role..._",
            winning_text="_and the winner is..._",
            emoji=None,
            use_padding=False,
            reactions=None,
        )
