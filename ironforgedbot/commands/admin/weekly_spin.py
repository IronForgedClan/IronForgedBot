import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Literal

import discord
from discord.ui import View

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.payment_embed import build_payment_embed, load_flavor_text
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.common.text_formatting import pad_winner_text
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
WEEKLY_SPIN_VIEW_TIMEOUT_SECONDS = 18 * 60 * 60
REROLL_PAYMENT_TIMEOUT_SECONDS = 30
REROLL_PAYMENT_TITLE = "\U0001f4b0 Re-roll Weekly Spin"
LOCK_PAYMENT_TITLE = "\U0001f4b0 Lock Weekly Spin"
REVEAL_DELAY_SECONDS = 10.5
LOCK_COST = 10000
LOCK_WINDOW_SECONDS = 60
LOCK_EMOJI = "\U0001f512"
UNLOCK_EMOJI = "\U0001f513"
NO_MENTIONS = discord.AllowedMentions.none()


@dataclass(frozen=True)
class PendingReroll:
    winner: str
    emoji: str
    mention: str
    timestamp: int


THUMBS_UP = "\U0001f44d"
THUMBS_DOWN = "\U0001f44e"

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


def _build_consolidated_history_line(
    winner_emoji: str,
    previous_winner: str,
    user_mention: str,
    ts: int,
    *,
    icon: str | None,
) -> str:
    """Single history line per reroll.

    Carries the previous-winner emoji, the struck-through previous winner,
    the rigger, a Discord relative timestamp captured at reroll time, and
    (optionally) the decision icon. ``icon=None`` yields the no-decision
    form; the two production callers (Don't Lock click and timer expiry)
    both pass ``UNLOCK_EMOJI`` so timer expiry renders identically to an
    explicit Don't Lock. The winner emoji leads the spoiler heading.
    """
    line = (
        f"{winner_emoji} ~~{previous_winner}~~ rerolled by {user_mention} "
        f"<t:{ts}:R>"
    )
    if icon is not None:
        line = f"{line} {icon}"
    return line


def _build_event_schedule_paragraph(
    start_ts: int,
    end_ts: int,
    reroll_close_ts: int | None = None,
) -> str:
    paragraph = f"This event will start on <t:{start_ts}:D> and end on <t:{end_ts}:D>."
    if reroll_close_ts is not None:
        paragraph += f" The active option will automatically be locked <t:{reroll_close_ts}:R>, unless a member locks their reroll."
        ingot_icon = find_emoji("Ingot") or ":Ingot:"
        paragraph += (
            f" Re-rolling costs {ingot_icon} **{REROLL_COST:,}** ingots and "
            f"locking costs {ingot_icon} **{LOCK_COST:,}** ingots."
        )
    return paragraph


def _build_spin_headings(kind: WeeklySpinKind, winner: str | None) -> list[str]:
    _validate_kind(kind)
    title = f"# {find_emoji('DWH') or ':DWH:'} The next {kind.upper()} is..."
    if winner is None:
        winner_heading = "## ..."
    else:
        winner_emoji = _lookup_emoji(kind, winner)
        padded_winner = pad_winner_text(winner_emoji, winner)
        winner_heading = f"## ||{padded_winner}||"
    return [title, winner_heading]


def _build_history_section(history_lines: list[str]) -> list[str]:
    if not history_lines:
        return []
    return ["### History", *(f"-# {line}" for line in history_lines)]


def _build_post_content(
    kind: WeeklySpinKind,
    winner: str,
    history_lines: list[str],
    start_ts: int,
    end_ts: int,
    reroll_close_ts: int | None = None,
) -> str:
    """Compose revealed post content with the winner in a padded spoiler heading."""
    headings = _build_spin_headings(kind, winner)
    event_schedule_paragraph = _build_event_schedule_paragraph(
        start_ts, end_ts, reroll_close_ts
    )
    history_section = _build_history_section(history_lines)
    content_lines = [
        *headings,
        "",
        event_schedule_paragraph,
        "",
        *history_section,
    ]
    if not history_section:
        content_lines.append("")
    return "\n".join(content_lines)


def _build_pending_content(
    kind: WeeklySpinKind,
    history_lines: list[str],
    start_ts: int,
    end_ts: int,
    reroll_close_ts: int | None = None,
) -> str:
    """Compose post content while the result is still pending reveal.

    Keep both heading lines stable during reveal. The H2 winner placeholder is
    replaced with the spoiler-tagged winner after the reveal delay.
    """
    headings = _build_spin_headings(kind, None)
    event_schedule_paragraph = _build_event_schedule_paragraph(
        start_ts, end_ts, reroll_close_ts
    )
    history_section = _build_history_section(history_lines)
    content_lines = [
        *headings,
        "",
        event_schedule_paragraph,
        "",
        *history_section,
    ]
    if not history_section:
        content_lines.append("")
    return "\n".join(content_lines)


def _build_lock_window_content(
    kind: WeeklySpinKind,
    winner: str,
    history_lines: list[str],
    user_mention: str,
    lock_close_ts: int,
    start_ts: int,
    end_ts: int,
    reroll_close_ts: int | None = None,
) -> str:
    """Compose post content during the 60s lock-decision window.

    Identifies the reroller and displays their lock-decision deadline.
    """
    headings = _build_spin_headings(kind, winner)
    event_schedule_paragraph = _build_event_schedule_paragraph(
        start_ts, end_ts, reroll_close_ts
    )
    lock_decision_sentence = (
        f":warning: {user_mention} has rerolled and must decide whether to lock "
        f"the result before the opportunity expires <t:{lock_close_ts}:R>."
    )
    history_section = _build_history_section(history_lines)
    content_lines = [*headings, "", event_schedule_paragraph, "", *history_section]
    if history_section:
        content_lines.append("")
    content_lines.append(lock_decision_sentence)
    return "\n".join(content_lines)


def _build_locked_content(
    self,
    history_lines: list[str],
) -> str:
    """Compose post content for the terminal locked state.

    Keeps the reroll + lock-decision history and strips the footers. All
    buttons are removed at the View level; this helper just produces the body.

    Sentences reflect the duration and the locked timestamp captured when
    the rigger paid the lock cost.
    """
    kind = self.kind
    winner = self.current_winner or ""
    start_ts = self._start_ts
    end_ts = self._end_ts
    locked_at = self._locked_at
    headings = _build_spin_headings(kind, winner)
    event_schedule_paragraph = _build_event_schedule_paragraph(start_ts, end_ts)
    locked_sentence = (
        f"{LOCK_EMOJI} Locked <t:{locked_at}:R>. The reroll window is now closed."
        if locked_at
        else f"{LOCK_EMOJI} The reroll window is now closed."
    )
    history_section = _build_history_section(history_lines)
    content_lines = [*headings, "", event_schedule_paragraph, "", locked_sentence, ""]
    content_lines.extend(history_section)
    return "\n".join(content_lines)


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
    for existing_key, timestamps in tuple(_recent_rerolls.items()):
        active_timestamps = [
            timestamp for timestamp in timestamps if now - timestamp < window_seconds
        ]
        if active_timestamps:
            _recent_rerolls[existing_key] = active_timestamps
        else:
            del _recent_rerolls[existing_key]

    key = (user_id, kind)
    recent = _recent_rerolls.get(key, [])
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


def _reroll_deadline_reached(view: "WeeklySpinView") -> bool:
    return time.time() >= view.created_at + WEEKLY_SPIN_VIEW_TIMEOUT_SECONDS


async def _expire_weekly_spin_after_delay(view: "WeeklySpinView", delay: float) -> None:
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return
    await view._timeout_at_deadline()


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


async def _refund_reroll_cost(user_id: int, reason: str) -> bool:
    try:
        async with db.get_session() as session:
            ingot_service = create_ingot_service(session)
            result = await ingot_service.try_add_ingots(
                user_id,
                REROLL_COST,
                None,
                f"Refund weekly spin reroll after {reason}",
            )
        return result.status
    except Exception:
        logger.exception(f"Failed to refund weekly spin reroll for user {user_id}")
        return False


async def _reveal_winner_after_delay(
    message: discord.Message,
    view: "WeeklySpinView",
    kind: WeeklySpinKind,
    winner: str,
    history_lines: list[str],
    reroll_close_ts: int,
) -> None:
    """Background task: wait REVEAL_DELAY_SECONDS, then reveal winner in H2.

    Skips the edit if the view has already timed out.

    If a lock-decision window is active when the reveal fires (the rigger's
    60s timer started at the same moment as the reroll, so they typically
    overlap), the lock-window footer is preserved instead of being replaced
    with the standard ``Re-roll window closes`` footer.
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

    # Defensive: if the user locked before reveal fired, do not overwrite
    # the locked content. ``_close_lock_window_as_locked`` cancels the
    # reveal task but a missed cancel (process restart, race) could leave
    # us here — bail out cleanly instead.
    if view._is_locked:
        logger.debug(f"Spin reveal skipped for message {message.id}: view is locked")
        return

    view._reroll_unlocked = True
    view._apply_button_state()

    if view._lock_window_active and view._lock_window_user_id is not None:
        content = _build_lock_window_content(
            kind,
            winner,
            history_lines,
            f"<@{view._lock_window_user_id}>",
            view._lock_window_end_ts,
            view._start_ts,
            view._end_ts,
            reroll_close_ts=reroll_close_ts,
        )
    else:
        content = _build_post_content(
            kind,
            winner,
            history_lines,
            view._start_ts,
            view._end_ts,
            reroll_close_ts=reroll_close_ts,
        )
    try:
        await message.edit(
            content=content,
            view=view,
            allowed_mentions=NO_MENTIONS,
        )
        logger.debug(
            f"Revealed {kind.upper()} winner {winner!r} after {REVEAL_DELAY_SECONDS}s delay"
        )
    except discord.HTTPException as e:
        logger.warning(f"Failed to reveal spin result for message {message.id}: {e}")


async def _lock_window_timer(
    view: "WeeklySpinView",
    message: discord.Message | None,
) -> None:
    """Background task: wait ``LOCK_WINDOW_SECONDS``, then close the window.

    Mirrors the cancellation discipline of ``_reveal_winner_after_delay``.
    Closing silently (no history line) implements the "default = don't lock"
    semantics on timeout. Keep the window open while a lock payment prompt is
    active so payment cannot race the timeout.
    """
    try:
        await asyncio.sleep(LOCK_WINDOW_SECONDS)
        while view._lock_completed and view._lock_window_active:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.debug("Lock window timer cancelled")
        raise

    if view._timed_out or not view._lock_window_active:
        return

    await view._close_lock_window_as_open(
        message=message,
        history_icon=UNLOCK_EMOJI,
    )


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
    start_ts: int,
    end_ts: int,
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
    placeholder_view._start_ts = start_ts
    placeholder_view._end_ts = end_ts
    close_ts = _reroll_close_ts(placeholder_view)
    pending_content = _build_pending_content(
        kind, [], start_ts, end_ts, reroll_close_ts=close_ts
    )

    msg = await target.send(
        file=file,
        content=pending_content,
        view=placeholder_view,
        allowed_mentions=NO_MENTIONS,
    )
    placeholder_view.target_message = msg
    deadline_delay = max(
        0,
        placeholder_view.created_at + WEEKLY_SPIN_VIEW_TIMEOUT_SECONDS - time.time(),
    )
    placeholder_view._deadline_task = asyncio.create_task(
        _expire_weekly_spin_after_delay(placeholder_view, deadline_delay),
        name=f"spin_deadline_{msg.id}",
    )

    await _add_default_reactions(msg)

    _schedule_reveal(placeholder_view, msg, kind, winner, [], close_ts)

    logger.debug(f"Posted {kind.upper()} weekly spin (pending reveal): {winner}")
    return msg


class WeeklySpinView(View):
    """View attached to the spin post. Member-only re-roll trigger.

    State machine
    -------------
    The Re-roll button's enabled-ness is the conjunction of three gates:

    - ``reroll_locked``: True while a single user is in the payment flow
      (prevents concurrent rerolls on the same post).
    - ``_reroll_unlocked``: False while the result is still pending reveal
      (prevents re-rolls before the winner is visible). Flipped to True by
      the background reveal task after REVEAL_DELAY_SECONDS.
    - ``_lock_window_active``: True for LOCK_WINDOW_SECONDS after a reroll
      while the rigger decides whether to lock the result. Disabled
      automatically by the lock-window close helpers.
    - ``_is_locked``: True once the rigger pays the lock cost or the view
      expires. Terminal — all buttons are removed and the event is over.
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
        self._timeout_finalized: bool = False
        self._timeout_lock = asyncio.Lock()
        self._deadline_task: asyncio.Task | None = None
        self._reroll_confirmation_task: asyncio.Task | None = None
        self._reroll_release_count: int = 0

        # Lock-decision window state.
        self._lock_window_active: bool = False
        self._lock_window_end_ts: int = 0
        self._lock_window_generation: int = 0
        self._lock_window_user_id: int | None = None
        self._is_locked: bool = False
        self._lock_window_task: asyncio.Task | None = None
        self._lock_completed: bool = False

        # Reroll data held between confirm_button and the lock-window
        # decision so the consolidated history line can be emitted once at
        # decision time. None when no decision is pending.
        self._pending_reroll: PendingReroll | None = None

        # Spin window dates (UTC midnight timestamps). Set by
        # ``post_weekly_spin_result`` right after construction; default 0
        # so existing tests that don't exercise the modal flow still work.
        self._start_ts: int = 0
        self._end_ts: int = 0
        # UTC timestamp captured the moment the rigger paid the lock
        # cost; surfaces in the locked-content sentence. 0 = not locked.
        self._locked_at: int = 0

        self._reroll_button = discord.ui.Button(
            label="Re-roll",
            style=discord.ButtonStyle.blurple,
            custom_id="weekly_spin_reroll",
            emoji="\U0001f504",
            row=0,
        )
        self._reroll_button.callback = self._on_reroll
        self.add_item(self._reroll_button)

        # Lock buttons are pre-built but NOT added to the view until the
        # lock-decision window opens. They're stored on the instance so
        # `_open_lock_window` can flip them in/out with a single add_item /
        # remove_item pair.
        self._lock_button = discord.ui.Button(
            label="Lock",
            style=discord.ButtonStyle.green,
            custom_id="weekly_spin_lock",
            emoji=LOCK_EMOJI,
            row=0,
        )
        self._lock_button.callback = self._on_lock

        self._dont_lock_button = discord.ui.Button(
            label="Don't Lock",
            style=discord.ButtonStyle.gray,
            custom_id="weekly_spin_dont_lock",
            emoji=UNLOCK_EMOJI,
            row=0,
        )
        self._dont_lock_button.callback = self._on_dont_lock

        self._apply_button_state()

    def _apply_button_state(self) -> None:
        """Sync the Re-roll button's ``disabled`` flag from the current gates.

        Lock/Don't-Lock buttons are added/removed from the view dynamically;
        their visibility is not driven by ``disabled`` alone.
        """
        reroll_disabled = (
            self.reroll_locked
            or not self._reroll_unlocked
            or self._lock_window_active
            or self._is_locked
            or self._timed_out
            or _reroll_deadline_reached(self)
        )
        self._reroll_button.disabled = reroll_disabled

    def _deadline_has_passed(self) -> bool:
        return self._timed_out or _reroll_deadline_reached(self)

    def _request_deadline_expiry(self) -> None:
        self._timed_out = True
        self._apply_button_state()
        if self._timeout_finalized or self._timeout_lock.locked():
            return
        if self._deadline_task is None or self._deadline_task.done():
            self._deadline_task = asyncio.create_task(
                self._timeout_at_deadline(),
                name=f"spin_deadline_{self.target_message.id if self.target_message else 0}",
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self._deadline_has_passed():
            self._request_deadline_expiry()
            await interaction.response.send_message(
                "The reroll window has closed.", ephemeral=True
            )
            return False
        if self._is_locked:
            await interaction.response.send_message(
                "This spin has been locked.", ephemeral=True
            )
            return False
        if self.reroll_locked:
            await interaction.response.send_message(
                "A re-roll is already in progress.", ephemeral=True
            )
            return False
        # The rigger already knows what they rerolled to, so they get to
        # bypass the reveal-state gate during the lock window. Everyone
        # else still gets the "pending reveal" deny so they can't peek
        # before the spoiler tag flips.
        is_rigger = (
            self._lock_window_active
            and interaction.user.id == self._lock_window_user_id
        )
        if not self._reroll_unlocked and not is_rigger:
            await interaction.response.send_message(
                "Result is pending reveal. Try again in a moment.", ephemeral=True
            )
            return False
        if self._lock_window_active and not is_rigger:
            await interaction.response.send_message(
                "Only the player who rerolled can decide whether to lock.",
                ephemeral=True,
            )
            return False
        role_names = {r.name for r in interaction.user.roles}
        if ROLE.MEMBER not in role_names:
            await interaction.response.send_message(
                "Member role required.", ephemeral=True
            )
            return False
        return True

    async def _timeout_at_deadline(self) -> None:
        async with self._timeout_lock:
            if self._timeout_finalized:
                return

            self._timed_out = True
            self._apply_button_state()
            current_task = asyncio.current_task()
            for task in (self._lock_window_task, self._reveal_task):
                if task is not None and not task.done() and task is not current_task:
                    task.cancel()
            if self._reveal_task is not None and self._reveal_task is not current_task:
                self._reveal_task = None

            while (
                self.reroll_locked
                or self._lock_completed
                or self._reroll_release_count > 0
                or (
                    self._reroll_confirmation_task is not None
                    and self._reroll_confirmation_task is not current_task
                    and not self._reroll_confirmation_task.done()
                )
            ):
                await asyncio.sleep(0.1)

            if (
                self._deadline_task is not None
                and self._deadline_task is not current_task
            ):
                self._deadline_task.cancel()
                self._deadline_task = None

            self._lock_window_active = False
            if self.current_winner is not None:
                self._is_locked = True
                if self._pending_reroll is not None:
                    self.history_lines.append(
                        _build_consolidated_history_line(
                            self._pending_reroll.emoji,
                            self._pending_reroll.winner,
                            self._pending_reroll.mention,
                            self._pending_reroll.timestamp,
                            icon=LOCK_EMOJI,
                        )
                    )
                    self._pending_reroll = None

            for item in (
                self._lock_button,
                self._dont_lock_button,
                self._reroll_button,
            ):
                if item in self.children:
                    self.remove_item(item)

            self._timeout_finalized = True
            self.stop()
            if self.target_message is not None:
                if self._is_locked:
                    edit_kwargs = {
                        "content": _build_locked_content(self, self.history_lines),
                        "view": None,
                        "allowed_mentions": NO_MENTIONS,
                    }
                elif self.current_winner is not None:
                    edit_kwargs = {
                        "content": _build_post_content(
                            self.kind,
                            self.current_winner,
                            self.history_lines,
                            self._start_ts,
                            self._end_ts,
                        ),
                        "view": None,
                        "allowed_mentions": NO_MENTIONS,
                    }
                else:
                    edit_kwargs = {"view": None}
                try:
                    await self.target_message.edit(**edit_kwargs)
                except discord.HTTPException:
                    pass

    async def on_timeout(self) -> None:
        await self._timeout_at_deadline()
        return await super().on_timeout()

    async def _set_lock_disabled(self) -> None:
        """Lock the view for a concurrent reroll and update the button."""
        self.reroll_locked = True
        self._apply_button_state()
        if self.target_message is not None:
            try:
                await self.target_message.edit(view=self)
            except Exception:
                pass

    async def _release_concurrent_lock(self) -> None:
        """Release the concurrent reroll lock without touching the reveal lock."""
        self._reroll_release_count += 1
        self.reroll_locked = False
        self._apply_button_state()
        try:
            if (
                self.target_message is not None
                and not self._timed_out
                and not _reroll_deadline_reached(self)
            ):
                try:
                    await self.target_message.edit(view=self)
                except discord.HTTPException:
                    pass
        finally:
            self._reroll_release_count -= 1

    async def _open_lock_window(self, *, user_id: int) -> None:
        """Enter the LOCK_WINDOW state for ``user_id``.

        Cancels any prior lock-window task, adds the Lock/Don't-Lock buttons,
        edits the target message with the countdown footer, and schedules the
        background timer that closes the window silently after
        ``LOCK_WINDOW_SECONDS``.
        """
        if self._deadline_has_passed():
            self._request_deadline_expiry()
            return

        if self._lock_window_task is not None and not self._lock_window_task.done():
            self._lock_window_task.cancel()

        self._lock_window_active = True
        self._lock_window_generation += 1
        self._lock_window_user_id = user_id
        self._lock_window_end_ts = int(time.time()) + LOCK_WINDOW_SECONDS
        self._is_locked = False
        self._lock_completed = False

        self._apply_button_state()
        if self._lock_button not in self.children:
            self.add_item(self._lock_button)
        if self._dont_lock_button not in self.children:
            self.add_item(self._dont_lock_button)

        message = self.target_message
        if message is not None:
            content = _build_lock_window_content(
                self.kind,
                self.current_winner or "",
                self.history_lines,
                f"<@{self._lock_window_user_id}>",
                self._lock_window_end_ts,
                self._start_ts,
                self._end_ts,
                _reroll_close_ts(self),
            )
            try:
                await message.edit(
                    content=content,
                    view=self,
                    allowed_mentions=NO_MENTIONS,
                )
            except discord.HTTPException as e:
                logger.warning(f"Failed to open lock window: {e}")

        self._lock_window_task = asyncio.create_task(
            _lock_window_timer(self, message),
            name=f"spin_lock_window_{message.id if message is not None else 0}",
        )

    async def _close_lock_window_as_locked(self) -> None:
        """Terminal locked state: user paid, event is over.

        Removes all buttons, appends the consolidated history line for the
        pending reroll (capped with the lock icon), edits the target message
        with the locked content (no footer, 🔒 in status).

        Cancels pending reveal task so it cannot overwrite locked post content.
        """
        if self._lock_window_task is not None and not self._lock_window_task.done():
            self._lock_window_task.cancel()
        if self._reveal_task is not None and not self._reveal_task.done():
            self._reveal_task.cancel()
            self._reveal_task = None

        self._lock_window_active = False
        self._is_locked = True
        self._locked_at = int(time.time())

        if self._pending_reroll is not None:
            self.history_lines.append(
                _build_consolidated_history_line(
                    self._pending_reroll.emoji,
                    self._pending_reroll.winner,
                    self._pending_reroll.mention,
                    self._pending_reroll.timestamp,
                    icon=LOCK_EMOJI,
                )
            )
            self._pending_reroll = None

        for item in (
            self._lock_button,
            self._dont_lock_button,
            self._reroll_button,
        ):
            if item in self.children:
                self.remove_item(item)

        message = self.target_message
        if message is not None:
            content = _build_locked_content(self, self.history_lines)
            try:
                await message.edit(
                    content=content,
                    view=None,
                    allowed_mentions=NO_MENTIONS,
                )
            except discord.HTTPException as e:
                logger.warning(f"Failed to lock spin post: {e}")
        self._lock_completed = False

    async def _close_lock_window_as_open(
        self,
        *,
        message: discord.Message | None,
        history_icon: str,
    ) -> None:
        """Reopen state: user clicked Don't Lock or the timer timed out.

                Re-enables the Re-roll button immediately (no waiting on the reveal
                animation), removes the lock buttons, restores the standard footer,
                and appends the consolidated history line for the pending reroll
                capped with ``history_icon``. Both production callers (Don't Lock
                click and timer expiry) pass ``UNLOCK_EMOJI`` so timer expiry
                renders identically to an explicit Don't Lock.

        Cancels the pending reveal task — its job was to flip
        ``_reroll_unlocked`` and reveal the spoiler; we do both ourselves
        here so the post is immediately actionable.
        """
        if self._deadline_has_passed():
            self._lock_completed = False
            self._request_deadline_expiry()
            return

        # Skip self-cancel when the current task is the timer itself. cancel()
        # is a no-op on a finished task, but on a still-running self it raises
        # CancelledError at the next yield, which interrupts this function's
        # own trailing ``await message.edit(...)`` and leaves the spin post
        # stuck on the lock-window content while Python thinks the window is
        # closed (so subsequent button clicks look like "This interaction
        # failed" because the discord-side message and our Python state are
        # out of sync).
        current = asyncio.current_task()
        if (
            self._lock_window_task is not None
            and not self._lock_window_task.done()
            and current is not self._lock_window_task
        ):
            self._lock_window_task.cancel()
        if self._reveal_task is not None and not self._reveal_task.done():
            self._reveal_task.cancel()
            self._reveal_task = None

        self._lock_window_active = False
        self._reroll_unlocked = True

        if self._pending_reroll is not None:
            self.history_lines.append(
                _build_consolidated_history_line(
                    self._pending_reroll.emoji,
                    self._pending_reroll.winner,
                    self._pending_reroll.mention,
                    self._pending_reroll.timestamp,
                    icon=history_icon,
                )
            )
            self._pending_reroll = None

        for item in (self._lock_button, self._dont_lock_button):
            if item in self.children:
                self.remove_item(item)
        self._apply_button_state()

        if message is not None:
            content = _build_post_content(
                self.kind,
                self.current_winner or "",
                self.history_lines,
                self._start_ts,
                self._end_ts,
                reroll_close_ts=_reroll_close_ts(self),
            )
            try:
                await message.edit(
                    content=content,
                    view=self,
                    allowed_mentions=NO_MENTIONS,
                )
            except discord.HTTPException as e:
                logger.warning(f"Failed to close lock window: {e}")
        self._lock_completed = False

    # Discord's persistent-view machinery calls ``item.callback(interaction)``
    # with a single argument; our real handlers also need the Button instance
    # (so tests can introspect it). These thin adapters bridge the two.
    async def _on_reroll(self, interaction: discord.Interaction) -> None:
        await self.reroll_button(interaction, self._reroll_button)

    async def _on_lock(self, interaction: discord.Interaction) -> None:
        await self.lock_button(interaction, self._lock_button)

    async def _on_dont_lock(self, interaction: discord.Interaction) -> None:
        await self.dont_lock_button(interaction, self._dont_lock_button)

    async def reroll_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self._deadline_has_passed():
            self._request_deadline_expiry()
            await interaction.response.send_message(
                "The reroll window has closed.", ephemeral=True
            )
            return

        # Lock synchronously, before any await, so a second click arriving in
        # the same event-loop tick fails `interaction_check` immediately
        # instead of racing through defer / DB lookup / embed build.
        self.reroll_locked = True
        self._apply_button_state()
        try:
            # ACK immediately so the interaction token doesn't expire during the
            # slow balance lookup below.
            await interaction.response.defer(ephemeral=True)

            allowed, wait = _check_reroll_rate_limit(interaction.user.id, self.kind)
            if not allowed:
                minutes = (wait + 59) // 60
                await interaction.followup.send(
                    content=(
                        f"Reroll cap reached ({REROLL_HOURLY_LIMIT}/hour). "
                        f"Try again in ~{minutes} minute(s)."
                    ),
                    ephemeral=True,
                )
                await self._release_concurrent_lock()
                return

            async with db.get_session() as session:
                member_service = MemberService(session)
                member = await member_service.get_member_by_discord_id(
                    interaction.user.id
                )
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
        except Exception:
            await self._release_concurrent_lock()
            raise

    async def lock_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id != self._lock_window_user_id:
            await interaction.response.send_message(
                "Only the player who rerolled can decide whether to lock.",
                ephemeral=True,
            )
            return
        if self._lock_completed:
            return
        if not self._lock_window_active or self._is_locked:
            await interaction.response.send_message(
                "The lock window has closed.", ephemeral=True
            )
            return
        self._lock_completed = True
        lock_window_generation = self._lock_window_generation

        try:
            await interaction.response.defer(ephemeral=True)

            async with db.get_session() as session:
                member_service = MemberService(session)
                member = await member_service.get_member_by_discord_id(
                    interaction.user.id
                )
                user_balance = member.ingots if member else 0

            if (
                not self._lock_window_active
                or self._lock_window_generation != lock_window_generation
                or self._lock_window_user_id != interaction.user.id
            ):
                await self._release_lock_payment(lock_window_generation)
                await interaction.followup.send(
                    "The lock window has closed.", ephemeral=True
                )
                return

            try:
                flavor_text_options = load_flavor_text()
                flavor_text = f"*{random.choice(flavor_text_options)}*\n"
            except Exception as e:
                logger.error(f"Failed to load flavor text: {e}")
                flavor_text = ""

            embed = build_payment_embed(
                cost=LOCK_COST,
                user_balance=user_balance,
                flavor_text=flavor_text,
                title=LOCK_PAYMENT_TITLE,
            )

            view = LockPaymentView(
                parent_view=self,
                user_id=interaction.user.id,
                lock_window_generation=lock_window_generation,
            )
            view.message = await interaction.followup.send(
                embed=embed, view=view, ephemeral=True
            )
        except Exception:
            await self._release_lock_payment(lock_window_generation)
            raise

    async def _release_lock_payment(self, generation: int) -> None:
        if generation == self._lock_window_generation and not self._is_locked:
            self._lock_completed = False

    async def dont_lock_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id != self._lock_window_user_id:
            await interaction.response.send_message(
                "Only the player who rerolled can decide whether to lock.",
                ephemeral=True,
            )
            return
        if self._lock_completed:
            return
        self._lock_completed = True

        await interaction.response.defer(ephemeral=True)

        await self._close_lock_window_as_open(
            message=self.target_message,
            history_icon=UNLOCK_EMOJI,
        )


class LockPaymentView(View):
    """Ephemeral Confirm/Cancel view for lock payment."""

    def __init__(
        self,
        *,
        parent_view: WeeklySpinView,
        user_id: int,
        lock_window_generation: int,
    ):
        super().__init__(timeout=REROLL_PAYMENT_TIMEOUT_SECONDS)
        self.parent_view = parent_view
        self.user_id = user_id
        self.lock_window_generation = lock_window_generation
        self.message: discord.Message | None = None
        self.completed: bool = False

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
        if not self.completed:
            await self.parent_view._release_lock_payment(self.lock_window_generation)
        else:
            return await super().on_timeout()
        if self.message is not None:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass
        return await super().on_timeout()

    @discord.ui.button(
        label="Pay",
        style=discord.ButtonStyle.green,
        custom_id="weekly_lock_pay",
    )
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id != self.user_id:
            return await self._reject_other_user(interaction)
        if self.completed:
            return
        self.completed = True

        parent = self.parent_view
        try:
            if parent._deadline_has_passed():
                await interaction.response.edit_message(
                    content="The reroll window has closed.", embed=None, view=None
                )
                parent._request_deadline_expiry()
                return

            if (
                not parent._lock_window_active
                or parent._is_locked
                or parent._lock_window_user_id != self.user_id
                or parent._lock_window_generation != self.lock_window_generation
            ):
                await interaction.response.edit_message(
                    content="The lock window has closed.", embed=None, view=None
                )
                return

            if parent.target_message is None:
                await interaction.response.edit_message(
                    content="Original spin post no longer exists.",
                    embed=None,
                    view=None,
                )
                return

            await interaction.response.defer(ephemeral=True)
            self.message = await interaction.original_response()

            try:
                async with db.get_session() as session:
                    ingot_service = create_ingot_service(session)
                    result = await ingot_service.try_remove_ingots(
                        interaction.user.id,
                        -LOCK_COST,
                        None,
                        f"Lock weekly spin: {parent.kind.upper()}",
                    )
            except Exception:
                logger.exception(
                    f"Failed to charge lock cost for user {interaction.user.id}"
                )
                await interaction.followup.send(
                    "Lock payment could not be confirmed. Check your balance before "
                    "trying again; contact an admin if balance changed.",
                    ephemeral=True,
                )
                await self._delete_self(interaction)
                return

            if not result.status:
                ingot_icon = find_emoji("Ingot")
                error_embed = build_response_embed(
                    title="\u274c Insufficient Funds",
                    description=f"Locking costs {ingot_icon} **{LOCK_COST:,}**.",
                    color=discord.Colour.red(),
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                await self._delete_self(interaction)
                return

            await self._delete_self(interaction)
            await parent._close_lock_window_as_locked()
        finally:
            await parent._release_lock_payment(self.lock_window_generation)

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.red,
        custom_id="weekly_lock_cancel",
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            return await self._reject_other_user(interaction)
        if self.completed:
            return
        self.completed = True
        await interaction.response.defer(ephemeral=True)
        await self.parent_view._release_lock_payment(self.lock_window_generation)
        await self._delete_self(interaction)


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
        # Set synchronously inside `confirm_button` so concurrent Pay clicks
        # can short-circuit before any await. Mirrors the
        # change_discord_account_view `completed` flag pattern.
        self.completed: bool = False

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
        if not self.completed:
            await self.parent_view._release_concurrent_lock()
        else:
            return await super().on_timeout()
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
    ) -> None:
        if interaction.user.id != self.user_id:
            return await self._reject_other_user(interaction)
        if self.completed:
            return
        self.completed = True
        parent = self.parent_view
        current_task = asyncio.current_task()
        parent._reroll_confirmation_task = current_task
        try:
            if parent._deadline_has_passed():
                await interaction.response.edit_message(
                    content="The reroll window has closed.", embed=None, view=None
                )
                parent._request_deadline_expiry()
                return

            if parent.target_message is None:
                await interaction.response.send_message(
                    "Original spin post no longer exists.", ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)
            self.message = await interaction.original_response()

            try:
                async with db.get_session() as session:
                    ingot_service = create_ingot_service(session)
                    result = await ingot_service.try_remove_ingots(
                        interaction.user.id,
                        -REROLL_COST,
                        None,
                        f"Reroll weekly spin: {parent.kind.upper()}",
                    )
            except Exception:
                logger.exception(
                    f"Failed to charge reroll cost for user {interaction.user.id}"
                )
                await interaction.followup.send(
                    "Reroll payment could not be confirmed. Check your balance "
                    "before trying again; contact an admin if balance changed.",
                    ephemeral=True,
                )
                await self._delete_self(interaction)
                return

            if not result.status:
                ingot_icon = find_emoji("Ingot")
                error_embed = build_response_embed(
                    title="\u274c Insufficient Funds",
                    description=f"Re-roll costs {ingot_icon} **{REROLL_COST:,}**.",
                    color=discord.Colour.red(),
                )
                await interaction.followup.send(embed=error_embed)
                await self._delete_self(interaction)
                return

            await self._delete_self(interaction)

            previous_winner = parent.current_winner or ""
            reroll_options = [
                option for option in parent.options if option != previous_winner
            ]

            try:
                new_file, new_winner = await build_spin_gif_file(reroll_options)
            except Exception:
                logger.exception(
                    f"Re-roll GIF generation failed for user {interaction.user.id}"
                )
                await self._refund_failed_reroll(
                    interaction,
                    "GIF generation failure",
                )
                return

            new_content = _build_pending_content(
                parent.kind,
                parent.history_lines,
                parent._start_ts,
                parent._end_ts,
                reroll_close_ts=_reroll_close_ts(parent),
            )
            try:
                await parent.target_message.edit(
                    content=new_content,
                    attachments=[new_file],
                    view=parent,
                    allowed_mentions=NO_MENTIONS,
                )
            except Exception:
                logger.exception(
                    f"Failed to update spin post after reroll for user "
                    f"{interaction.user.id}"
                )
                await self._refund_failed_reroll(
                    interaction,
                    "spin post update failure",
                )
                return

            parent._pending_reroll = PendingReroll(
                winner=previous_winner,
                emoji=_lookup_emoji(parent.kind, previous_winner),
                mention=interaction.user.mention,
                timestamp=int(time.time()),
            )
            parent.current_winner = new_winner
            parent._reroll_unlocked = False
            parent._apply_button_state()

            _schedule_reveal(
                parent,
                parent.target_message,
                parent.kind,
                new_winner,
                parent.history_lines,
                _reroll_close_ts(parent),
            )

            await _reset_reactions(parent.target_message)
            await parent._open_lock_window(user_id=interaction.user.id)
            logger.debug(
                f"Reroll complete for user {interaction.user.id} ({parent.kind.upper()})"
            )
        finally:
            if parent._reroll_confirmation_task is current_task:
                parent._reroll_confirmation_task = None
            await parent._release_concurrent_lock()

    async def _refund_failed_reroll(
        self,
        interaction: discord.Interaction,
        reason: str,
    ) -> None:
        refunded = await _refund_reroll_cost(interaction.user.id, reason)
        if refunded:
            message = "Reroll failed; your ingots were refunded. Try again later."
        else:
            message = (
                "Reroll failed and refund could not be confirmed. Contact an admin "
                "before retrying."
            )
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.red,
        custom_id="weekly_reroll_cancel",
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id != self.user_id:
            return await self._reject_other_user(interaction)
        if self.completed:
            return
        self.completed = True
        await interaction.response.defer(ephemeral=True)
        await self.parent_view._release_concurrent_lock()
        await self._delete_self(interaction)
