import logging
import random
import time
from typing import Literal

import discord
from discord.ui import View

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.payment_embed import build_payment_embed, load_flavor_text
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.commands.spin.build_spin_gif import build_spin_gif_file
from ironforgedbot.services.service_factory import create_ingot_service
from ironforgedcore.common.roles import ROLE
from ironforgedcore.database import db
from ironforgedcore.services.member_service import MemberService
from ironforgedcore.storage import data

logger = logging.getLogger(__name__)

WeeklySpinKind = Literal["sotw", "botw"]

REROLL_COST = 2500
REROLL_HOURLY_LIMIT = 10
REROLL_WINDOW_SECONDS = 3600
WEEKLY_SPIN_VIEW_TIMEOUT_SECONDS = 86400
REROLL_PAYMENT_TIMEOUT_SECONDS = 30
REROLL_PAYMENT_TITLE = "\U0001f4b0 Re-roll Weekly Spin"

_recent_rerolls: dict[tuple[int, str], list[float]] = {}


def _lookup_emoji(kind: WeeklySpinKind, winner: str) -> str:
    """Resolve the display emoji for a winning option.

    SOTW: match against data.SKILLS by `name`.
    BOTW: BOTW options can be grouped (e.g. "Callisto or Artio") so the
    leading name is used for the lookup; the original `winner` string is
    preserved for display.
    """
    if kind == "sotw":
        skill = next((s for s in data.SKILLS if s["name"] == winner), None)
        if skill is None:
            return "\U0001f389"
        return find_emoji(skill["emoji_key"]) or "\U0001f389"

    if kind == "botw":
        boss_name = winner.split(" or ")[0]
        boss = next((b for b in data.BOSSES if b["name"] == boss_name), None)
        if boss is None:
            return "\U0001f389"
        return find_emoji(boss["emoji_key"]) or "\U0001f389"

    raise ValueError(f"Unknown weekly spin kind: {kind!r}")


def _build_history_line(previous_winner: str, user_mention: str) -> str:
    return f"{previous_winner} rerolled by {user_mention}"


def _build_post_content(
    kind: WeeklySpinKind, winner: str, history_lines: list[str]
) -> str:
    """Compose the full post content: history lines + header + spoiler line."""
    header = f"## Next {kind.upper()}"
    spoiler = f"||{_lookup_emoji(kind, winner)} {winner}||"
    if history_lines:
        return "\n".join([*history_lines, header, spoiler])
    return f"{header}\n{spoiler}"


def _check_reroll_rate_limit(
    user_id: int,
    kind: WeeklySpinKind,
    *,
    limit: int = REROLL_HOURLY_LIMIT,
    window_seconds: int = REROLL_WINDOW_SECONDS,
    now: float | None = None,
) -> tuple[bool, int]:
    """Record a reroll attempt; return (allowed, seconds_until_next_slot).

    Per-kind, per-user sliding-window counter. Old timestamps are pruned
    on every call so memory stays bounded.
    """
    if now is None:
        now = time.time()
    key = (user_id, kind)
    recent = [t for t in _recent_rerolls.get(key, []) if now - t < window_seconds]
    if len(recent) >= limit:
        oldest = min(recent)
        wait = int(window_seconds - (now - oldest)) + 1
        _recent_rerolls[key] = recent
        return False, max(wait, 1)
    recent.append(now)
    _recent_rerolls[key] = recent
    return True, 0


async def post_weekly_spin_result(
    target: discord.abc.Messageable,
    kind: WeeklySpinKind,
    options: list[str],
    file: discord.File,
    winner: str,
) -> discord.Message:
    """Post a spin GIF plus the spoiler-tagged winner to the weekly channel.

    The header advertises which weekly pick this is (e.g. "## Next BOTW").
    The winner line is wrapped in Discord spoiler tags so viewers choose
    when to reveal it. Two thumb reactions (👍 / 👎) are added so members
    can vote without typing. A `WeeklySpinView` with a Re-roll button is
    attached so members can pay to spin again.
    """
    content = _build_post_content(kind, winner, [])

    placeholder_view = WeeklySpinView(options=options, kind=kind, target_message=None)
    placeholder_view.current_winner = winner
    msg = await target.send(file=file, content=content, view=placeholder_view)
    placeholder_view.target_message = msg

    await msg.add_reaction("\U0001f44d")
    await msg.add_reaction("\U0001f44e")

    logger.debug(f"Posted {kind.upper()} weekly spin result: {winner}")
    return msg


class WeeklySpinView(View):
    """View attached to the spin post. Member-only re-roll trigger."""

    def __init__(
        self,
        options: list[str],
        kind: WeeklySpinKind,
        target_message: discord.Message | None,
    ):
        super().__init__(timeout=WEEKLY_SPIN_VIEW_TIMEOUT_SECONDS)
        self.options = options
        self.kind = kind
        self.target_message = target_message
        self.reroll_locked: bool = False
        self.history_lines: list[str] = []
        self.current_winner: str | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.reroll_locked:
            await interaction.response.send_message(
                "A re-roll is already in progress.", ephemeral=True
            )
            return False
        role_names = {r.name for r in interaction.user.roles}
        if ROLE.MEMBER not in role_names:
            await interaction.response.send_message(
                "Member role required.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Item):
                child.disabled = True
        if self.target_message is not None:
            try:
                await self.target_message.edit(view=self)
            except discord.HTTPException:
                pass
        return await super().on_timeout()

    async def _set_lock_disabled(self) -> None:
        """Lock the view and visually disable buttons on the spin post."""
        self.reroll_locked = True
        for child in self.children:
            if isinstance(child, discord.ui.Item):
                child.disabled = True
        if self.target_message is not None:
            try:
                await self.target_message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(
        label="Re-roll",
        style=discord.ButtonStyle.blurple,
        custom_id="weekly_spin_reroll",
        emoji="\U0001f504",
    )
    async def reroll_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # ACK immediately so the interaction token doesn't expire during the
        # slow balance lookup below.
        await interaction.response.defer(ephemeral=True)

        allowed, wait = _check_reroll_rate_limit(interaction.user.id, self.kind)
        if not allowed:
            minutes = (wait + 59) // 60
            return await interaction.followup.send(
                content=(
                    f"Reroll cap reached ({REROLL_HOURLY_LIMIT}/hour). "
                    f"Try again in ~{minutes} minute(s)."
                ),
                ephemeral=True,
            )

        async with db.get_session() as session:
            member_service = MemberService(session)
            member = await member_service.get_member_by_discord_id(interaction.user.id)
            user_balance = member.ingots if member else 0

        try:
            flavor_text_options = load_flavor_text()
            flavor_text = f"*{random.choice(flavor_text_options)}*\n"
        except Exception as e:
            logger.error(f"Failed to load flavor text: {e}")
            flavor_text = ""

        embed = build_payment_embed(
            cost=REROLL_COST,
            user_balance=user_balance,
            flavor_text=flavor_text,
            title=REROLL_PAYMENT_TITLE,
        )

        await self._set_lock_disabled()

        view = RerollPaymentView(parent_view=self, user_id=interaction.user.id)
        view.message = await interaction.followup.send(
            embed=embed, view=view, ephemeral=True
        )


class RerollPaymentView(View):
    """Ephemeral Confirm/Cancel view for reroll payment."""

    def __init__(
        self,
        *,
        parent_view: WeeklySpinView,
        user_id: int,
    ):
        super().__init__(timeout=REROLL_PAYMENT_TIMEOUT_SECONDS)
        self.parent_view = parent_view
        self.user_id = user_id
        self.message: discord.Message | None = None

    async def _reject_other_user(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "This confirmation is not for you.", ephemeral=True
        )

    async def _delete_self(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

    async def _release_lock_and_re_enable(self) -> None:
        parent = self.parent_view
        parent.reroll_locked = False
        for child in parent.children:
            if isinstance(child, discord.ui.Item):
                child.disabled = False
        if parent.target_message is not None:
            try:
                await parent.target_message.edit(view=parent)
            except discord.HTTPException:
                pass

    async def on_timeout(self) -> None:
        await self._release_lock_and_re_enable()
        if self.message is not None:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass
        return await super().on_timeout()

    @discord.ui.button(
        label="Pay",
        style=discord.ButtonStyle.green,
        custom_id="weekly_reroll_pay",
    )
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            return await self._reject_other_user(interaction)
        parent = self.parent_view
        if parent.target_message is None:
            await interaction.response.send_message(
                "Original spin post no longer exists.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        self.message = await interaction.original_response()

        async with db.get_session() as session:
            ingot_service = create_ingot_service(session)
            result = await ingot_service.try_remove_ingots(
                interaction.user.id,
                -REROLL_COST,
                None,
                f"Reroll weekly spin: {parent.kind.upper()}",
            )

        ingot_icon = find_emoji("Ingot")

        if not result.status:
            error_embed = build_response_embed(
                title="\u274c Insufficient Funds",
                description=(f"Re-roll costs {ingot_icon} **{REROLL_COST:,}**."),
                color=discord.Colour.red(),
            )
            await interaction.followup.send(embed=error_embed)
            await self._release_lock_and_re_enable()
            await self._delete_self(interaction)
            return

        try:
            new_file, new_winner = await build_spin_gif_file(parent.options)
        except Exception as e:
            logger.error(f"Re-roll GIF generation failed: {e}")
            await interaction.followup.send(
                "Payment succeeded but generating the new GIF failed. "
                "Contact an admin.",
            )
            await self._release_lock_and_re_enable()
            await self._delete_self(interaction)
            return

        history_line = _build_history_line(
            parent.current_winner or "", interaction.user.mention
        )
        parent.history_lines.append(history_line)
        parent.current_winner = new_winner

        new_content = _build_post_content(parent.kind, new_winner, parent.history_lines)
        try:
            await parent.target_message.edit(
                content=new_content, attachments=[new_file]
            )
        except discord.HTTPException as e:
            logger.error(f"Failed to edit spin post for reroll: {e}")
            await interaction.followup.send(
                "Payment succeeded but updating the spin post failed.",
            )
            await self._release_lock_and_re_enable()
            await self._delete_self(interaction)
            return

        await self._release_lock_and_re_enable()
        await self._delete_self(interaction)
        logger.debug(
            f"Reroll complete for user {interaction.user.id} ({parent.kind.upper()})"
        )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.red,
        custom_id="weekly_reroll_cancel",
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            return await self._reject_other_user(interaction)
        await interaction.response.defer(ephemeral=True)
        await self._release_lock_and_re_enable()
        if self.message is not None:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass
