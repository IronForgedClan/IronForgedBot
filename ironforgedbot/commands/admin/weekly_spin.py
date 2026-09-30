import asyncio
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
REVEAL_DELAY_SECONDS = 10.5

THUMBS_UP = "\U0001f44d"
THUMBS_DOWN = "\U0001f44e"

# Strong references to background reveal tasks to prevent premature GC.
# Tasks are discarded via done callback when they complete.
_background_tasks: set[asyncio.Task] = set()

_recent_rerolls: dict[tuple[int, str], list[float]] = {}


def _validate_kind(kind: WeeklySpinKind) -> None:
    if kind not in ("sotw", "botw"):
        raise ValueError(f"Unknown weekly spin kind: {kind!r}")


def _lookup_emoji(kind: WeeklySpinKind, winner: str) -> str:
    """Resolve the display emoji for a winning option.

    SOTW: match against data.SKILLS by `name`.
    BOTW: BOTW options can be grouped (e.g. "Callisto or Artio") so the
    leading name is used for the lookup; the original `winner` string is
    preserved for display.
    """
    _validate_kind(kind)
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
    return f"~~{previous_winner}~~ rerolled by {user_mention}"


def _build_post_content(
    kind: WeeklySpinKind,
    winner: str,
    history_lines: list[str],
    reroll_close_ts: int | None = None,
) -> str:
    """Compose the full post content with the spoiler winner inside the header."""
    emoji = _lookup_emoji(kind, winner)
    header = f"# Next {kind.upper()} is ||{emoji} {winner}||"
    bulleted = [f"- {line}" for line in history_lines]
    parts = [header, *bulleted]
    if reroll_close_ts is not None:
        parts.append("")
        parts.append(f"-# Re-roll window closes <t:{reroll_close_ts}:R>.")
    return "\n".join(parts)


def _build_pending_content(
    kind: WeeklySpinKind,
    history_lines: list[str],
    reroll_close_ts: int | None = None,
) -> str:
    """Compose post content while the result is still pending reveal.

    Header ends with `...` to signal the result is incoming; the background
    reveal task replaces this with the spoiler-tagged winner.
    """
    _validate_kind(kind)
    header = f"# Next {kind.upper()} is..."
    bulleted = [f"- {line}" for line in history_lines]
    parts = [header, *bulleted]
    if reroll_close_ts is not None:
        parts.append("")
        parts.append(f"-# Re-roll window closes <t:{reroll_close_ts}:R>.")
    return "\n".join(parts)


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


def _reroll_close_ts(view: "WeeklySpinView") -> int:
    """Unix timestamp at which the view's re-roll window expires."""
    return int(view.created_at + WEEKLY_SPIN_VIEW_TIMEOUT_SECONDS)


async def _add_default_reactions(message: discord.Message) -> None:
    """Add the canonical 👍 + 👎 pair to a spin post.

    Failures (e.g. channel permissions) are logged but never raised — the
    spin flow must not fail just because the bot cannot add reactions.
    """
    try:
        await message.add_reaction(THUMBS_UP)
        await message.add_reaction(THUMBS_DOWN)
    except discord.HTTPException as e:
        logger.warning(f"Failed to add default reactions to {message.id}: {e}")


async def _reset_reactions(message: discord.Message) -> None:
    """Clear all reactions on the spin post and re-add the default pair.

    Members can vote fresh on each new spin result. Requires the Manage
    Messages permission on the channel — falls back to a warning if missing.
    """
    try:
        await message.clear_reactions()
    except discord.Forbidden:
        logger.warning(
            f"Cannot clear reactions on message {message.id} "
            "(missing Manage Messages permission)"
        )
        return
    except discord.HTTPException as e:
        logger.warning(f"Failed to clear reactions on {message.id}: {e}")
        return
    await _add_default_reactions(message)


async def _reveal_winner_after_delay(
    message: discord.Message,
    view: "WeeklySpinView",
    kind: WeeklySpinKind,
    winner: str,
    history_lines: list[str],
    reroll_close_ts: int,
) -> None:
    """Background task: wait REVEAL_DELAY_SECONDS, then edit the message to
    reveal the spoiler winner inside the header line.

    Skips the edit if the view has already timed out.
    """
    try:
        await asyncio.sleep(REVEAL_DELAY_SECONDS)
    except asyncio.CancelledError:
        logger.info(f"Spin reveal cancelled for message {message.id}")
        raise

    if view._timed_out:
        logger.debug(
            f"Spin reveal skipped for message {message.id}: view already timed out"
        )
        return

    view._reroll_unlocked = True
    view._apply_button_state()

    content = _build_post_content(
        kind, winner, history_lines, reroll_close_ts=reroll_close_ts
    )
    try:
        await message.edit(content=content, view=view)
        logger.debug(
            f"Revealed {kind.upper()} winner {winner!r} after {REVEAL_DELAY_SECONDS}s delay"
        )
    except discord.HTTPException as e:
        logger.warning(f"Failed to reveal spin result for message {message.id}: {e}")


def _schedule_reveal(
    view: "WeeklySpinView",
    message: discord.Message,
    kind: WeeklySpinKind,
    winner: str,
    history_lines: list[str],
    reroll_close_ts: int,
) -> None:
    """Cancel any prior reveal task on the view and schedule a new one."""
    if view._reveal_task is not None and not view._reveal_task.done():
        view._reveal_task.cancel()
    view._reveal_task = asyncio.create_task(
        _reveal_winner_after_delay(
            message, view, kind, winner, history_lines, reroll_close_ts
        ),
        name=f"spin_reveal_{message.id}",
    )


async def post_weekly_spin_result(
    target: discord.abc.Messageable,
    kind: WeeklySpinKind,
    options: list[str],
    file: discord.File,
    winner: str,
) -> discord.Message:
    """Post a spin GIF plus the pending-result header to the weekly channel.

    The initial post shows only the "Next X is..." header — the winner is
    revealed after REVEAL_DELAY_SECONDS via a background task that edits the
    message. Two thumb reactions (👍 / 👎) are added immediately so members
    can vote without typing. A `WeeklySpinView` with a Re-roll button is
    attached so members can pay to spin again.
    """
    placeholder_view = WeeklySpinView(options=options, kind=kind, target_message=None)
    placeholder_view.current_winner = winner
    close_ts = _reroll_close_ts(placeholder_view)
    pending_content = _build_pending_content(kind, [], reroll_close_ts=close_ts)

    msg = await target.send(file=file, content=pending_content, view=placeholder_view)
    placeholder_view.target_message = msg

    await _add_default_reactions(msg)

    _schedule_reveal(placeholder_view, msg, kind, winner, [], close_ts)

    logger.debug(f"Posted {kind.upper()} weekly spin (pending reveal): {winner}")
    return msg


class WeeklySpinView(View):
    """View attached to the spin post. Member-only re-roll trigger.

    Two independent locks govern the reroll button:

    - ``reroll_locked``: True while a single user is in the payment flow
      (prevents concurrent rerolls on the same post).
    - ``_reroll_unlocked``: False while the result is still pending reveal
      (prevents re-rolls before the winner is visible). Flipped to True by
      the background reveal task after REVEAL_DELAY_SECONDS.

    The button's ``disabled`` flag is ``reroll_locked or not _reroll_unlocked``.
    """

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
        self._reroll_unlocked: bool = False
        self.history_lines: list[str] = []
        self.current_winner: str | None = None
        self.created_at: float = time.time()
        self._reveal_task: asyncio.Task | None = None
        self._timed_out: bool = False

        self._apply_button_state()

    def _apply_button_state(self) -> None:
        """Sync each child's ``disabled`` from current lock flags."""
        disabled = self.reroll_locked or not self._reroll_unlocked
        for child in self.children:
            if isinstance(child, discord.ui.Item):
                child.disabled = disabled

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.reroll_locked:
            await interaction.response.send_message(
                "A re-roll is already in progress.", ephemeral=True
            )
            return False
        if not self._reroll_unlocked:
            await interaction.response.send_message(
                "Result is pending reveal. Try again in a moment.", ephemeral=True
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
        self._timed_out = True
        for child in self.children:
            if isinstance(child, discord.ui.Item):
                child.disabled = True
        if self.target_message is not None:
            edit_kwargs: dict = {"view": self}
            if self.current_winner is not None:
                edit_kwargs["content"] = _build_post_content(
                    self.kind, self.current_winner, self.history_lines
                )
            try:
                await self.target_message.edit(**edit_kwargs)
            except discord.HTTPException:
                pass
        return await super().on_timeout()

    async def _set_lock_disabled(self) -> None:
        """Lock the view for a concurrent reroll and update the button."""
        self.reroll_locked = True
        self._apply_button_state()
        if self.target_message is not None:
            try:
                await self.target_message.edit(view=self)
            except discord.HTTPException:
                pass

    async def _release_concurrent_lock(self) -> None:
        """Release the concurrent reroll lock without touching the reveal lock."""
        self.reroll_locked = False
        self._apply_button_state()
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

    async def on_timeout(self) -> None:
        await self.parent_view._release_concurrent_lock()
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
            await parent._release_concurrent_lock()
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
            await parent._release_concurrent_lock()
            await self._delete_self(interaction)
            return

        history_line = _build_history_line(
            parent.current_winner or "", interaction.user.mention
        )
        parent.history_lines.append(history_line)
        parent.current_winner = new_winner
        parent._reroll_unlocked = False
        parent._apply_button_state()

        new_content = _build_pending_content(
            parent.kind,
            parent.history_lines,
            reroll_close_ts=_reroll_close_ts(parent),
        )
        try:
            await parent.target_message.edit(
                content=new_content, attachments=[new_file], view=parent
            )
        except discord.HTTPException as e:
            logger.error(f"Failed to edit spin post for reroll: {e}")
            await interaction.followup.send(
                "Payment succeeded but updating the spin post failed.",
            )
            await parent._release_concurrent_lock()
            await self._delete_self(interaction)
            return

        _schedule_reveal(
            parent,
            parent.target_message,
            parent.kind,
            new_winner,
            parent.history_lines,
            _reroll_close_ts(parent),
        )

        await _reset_reactions(parent.target_message)

        await parent._release_concurrent_lock()
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
        await self.parent_view._release_concurrent_lock()
        if self.message is not None:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass
