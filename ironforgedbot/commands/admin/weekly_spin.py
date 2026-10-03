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
LOCK_COST = 10000
LOCK_WINDOW_SECONDS = 60
LOCK_EMOJI = "\U0001f512"
UNLOCK_EMOJI = "\U0001f513"

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
    explicit Don't Lock. The emoji uses the same leading position as the
    post header (``||emoji winner||``).
    """
    line = (
        f"{winner_emoji} ~~{previous_winner}~~ rerolled by {user_mention} "
        f"<t:{ts}:R>"
    )
    if icon is not None:
        line = f"{line} {icon}"
    return line


def _build_post_content(
    kind: WeeklySpinKind,
    winner: str,
    history_lines: list[str],
    start_ts: int,
    end_ts: int,
    reroll_close_ts: int | None = None,
) -> str:
    """Compose the full post content with the spoiler winner inside the header."""
    emoji = _lookup_emoji(kind, winner)
    header = f"# Next {kind.upper()} is ||{emoji} {winner}||"
    dates = f"<t:{start_ts}:D> → <t:{end_ts}:D>"
    bulleted = [f"- {line}" for line in history_lines]
    parts = [header, dates, *bulleted]
    if reroll_close_ts is not None:
        parts.append("")
        parts.append(f"-# Re-roll window closes <t:{reroll_close_ts}:R>.")
    return "\n".join(parts)


def _build_pending_content(
    kind: WeeklySpinKind,
    history_lines: list[str],
    start_ts: int,
    end_ts: int,
    reroll_close_ts: int | None = None,
) -> str:
    """Compose post content while the result is still pending reveal.

    Header ends with `...` to signal the result is incoming; the background
    reveal task replaces this with the spoiler-tagged winner.
    """
    _validate_kind(kind)
    header = f"# Next {kind.upper()} is..."
    dates = f"<t:{start_ts}:D> → <t:{end_ts}:D>"
    bulleted = [f"- {line}" for line in history_lines]
    parts = [header, dates, *bulleted]
    if reroll_close_ts is not None:
        parts.append("")
        parts.append(f"-# Re-roll window closes <t:{reroll_close_ts}:R>.")
    return "\n".join(parts)


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

    The status line is plain text (the :warning: emoji carries the urgency),
    and the countdown uses Discord's relative timestamp (``<t:TS:R>``) so it
    auto-updates as time passes without us having to edit the message every
    tick. The trailing reroll-window footer is small italic and references
    the 24h view timeout.
    """
    emoji = _lookup_emoji(kind, winner)
    header = f"# Next {kind.upper()} is ||{emoji} {winner}||"
    dates = f"<t:{start_ts}:D> → <t:{end_ts}:D>"
    bulleted = [f"- {line}" for line in history_lines]
    parts = [header, dates, *bulleted, ""]
    parts.append(
        f":warning: {user_mention} has rerolled and now has "
        f"<t:{lock_close_ts}:R> to decide to lock or not."
    )
    if reroll_close_ts is not None:
        parts.append("")
        parts.append(f"-# Re-roll window closes <t:{reroll_close_ts}:R>.")
    return "\n".join(parts)


def _build_locked_content(
    kind: WeeklySpinKind,
    winner: str,
    history_lines: list[str],
    start_ts: int,
    end_ts: int,
) -> str:
    """Compose post content for the terminal locked state.

    Adds the lock emoji to the header, keeps the reroll + lock-decision
    history, and strips the footers. All buttons are removed at the View
    level; this helper just produces the body.
    """
    emoji = _lookup_emoji(kind, winner)
    header = f"# Next {kind.upper()} is ||{emoji} {winner}|| {LOCK_EMOJI}"
    dates = f"<t:{start_ts}:D> → <t:{end_ts}:D>"
    bulleted = [f"- {line}" for line in history_lines]
    return "\n".join([header, dates, *bulleted])


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
        await message.edit(content=content, view=view)
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
    semantics on timeout.
    """
    try:
        await asyncio.sleep(LOCK_WINDOW_SECONDS)
    except asyncio.CancelledError:
        logger.debug("Lock window timer cancelled")
        raise

    if view._timed_out:
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

    msg = await target.send(file=file, content=pending_content, view=placeholder_view)
    placeholder_view.target_message = msg

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
    - ``_is_locked``: True once the rigger pays the lock cost. Terminal —
      all buttons are removed and the event is over.
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

        # Lock-decision window state.
        self._lock_window_active: bool = False
        self._lock_window_end_ts: int = 0
        self._lock_window_user_id: int | None = None
        self._is_locked: bool = False
        self._lock_window_task: asyncio.Task | None = None
        self._lock_completed: bool = False

        # Reroll data held between confirm_button and the lock-window
        # decision so the consolidated history line can be emitted once at
        # decision time. None when no decision is pending.
        self._pending_reroll: dict | None = None

        # Spin window dates (UTC midnight timestamps). Set by
        # ``post_weekly_spin_result`` right after construction; default 0
        # so existing tests that don't exercise the modal flow still work.
        self._start_ts: int = 0
        self._end_ts: int = 0

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
        )
        self._reroll_button.disabled = reroll_disabled

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
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

    async def on_timeout(self) -> None:
        self._timed_out = True
        if self._lock_window_task is not None and not self._lock_window_task.done():
            self._lock_window_task.cancel()
        for item in (
            self._lock_button,
            self._dont_lock_button,
            self._reroll_button,
        ):
            if item in self.children:
                self.remove_item(item)
        if self.target_message is not None:
            if self._is_locked:
                edit_kwargs = {
                    "content": _build_locked_content(
                        self.kind,
                        self.current_winner or "",
                        self.history_lines,
                        self._start_ts,
                        self._end_ts,
                    ),
                    "view": None,
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
                }
            else:
                edit_kwargs = {"view": None}
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

    async def _open_lock_window(self, *, user_id: int) -> None:
        """Enter the LOCK_WINDOW state for ``user_id``.

        Cancels any prior lock-window task, adds the Lock/Don't-Lock buttons,
        edits the target message with the countdown footer, and schedules the
        background timer that closes the window silently after
        ``LOCK_WINDOW_SECONDS``.
        """
        if self._lock_window_task is not None and not self._lock_window_task.done():
            self._lock_window_task.cancel()

        self._lock_window_active = True
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
                f"<@{user_id}>",
                self._lock_window_end_ts,
                self._start_ts,
                self._end_ts,
                _reroll_close_ts(self),
            )
            try:
                await message.edit(content=content, view=self)
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
        with the locked content (no footer, 🔒 in header).

        Cancels the pending reveal task — if it fired later it would
        overwrite the 🔒 header with a plain spoiler header.
        """
        if self._lock_window_task is not None and not self._lock_window_task.done():
            self._lock_window_task.cancel()
        if self._reveal_task is not None and not self._reveal_task.done():
            self._reveal_task.cancel()
            self._reveal_task = None

        self._lock_window_active = False
        self._is_locked = True

        if self._pending_reroll is not None:
            self.history_lines.append(
                _build_consolidated_history_line(
                    self._pending_reroll["emoji"],
                    self._pending_reroll["winner"],
                    self._pending_reroll["mention"],
                    self._pending_reroll["ts"],
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
            content = _build_locked_content(
                self.kind,
                self.current_winner or "",
                self.history_lines,
                self._start_ts,
                self._end_ts,
            )
            try:
                await message.edit(content=content, view=None)
            except discord.HTTPException as e:
                logger.warning(f"Failed to lock spin post: {e}")

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
                    self._pending_reroll["emoji"],
                    self._pending_reroll["winner"],
                    self._pending_reroll["mention"],
                    self._pending_reroll["ts"],
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
                await message.edit(content=content, view=self)
            except discord.HTTPException as e:
                logger.warning(f"Failed to close lock window: {e}")

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
    ):
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
    ):
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

        async with db.get_session() as session:
            ingot_service = create_ingot_service(session)
            result = await ingot_service.try_remove_ingots(
                interaction.user.id,
                -LOCK_COST,
                None,
                f"Lock weekly spin: {self.kind.upper()}",
            )

        if not result.status:
            ingot_icon = find_emoji("Ingot")
            error_embed = build_response_embed(
                title="\u274c Insufficient Funds",
                description=f"Locking costs {ingot_icon} **{LOCK_COST:,}**.",
                color=discord.Colour.red(),
            )
            await interaction.followup.send(embed=error_embed)
            # Allow another lock attempt within the same window.
            self._lock_completed = False
            return

        await self._close_lock_window_as_locked()

    async def dont_lock_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
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
        if self.completed:
            return
        self.completed = True
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

        # Drop the payment embed immediately after debit succeeds; the slow
        # GIF build / message edit / reveal schedule that follows doesn't
        # need the user staring at the prompt.
        await self._delete_self(interaction)

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

        parent._pending_reroll = {
            "winner": parent.current_winner or "",
            "emoji": _lookup_emoji(parent.kind, parent.current_winner or ""),
            "mention": interaction.user.mention,
            "ts": int(time.time()),
        }
        parent.current_winner = new_winner
        parent._reroll_unlocked = False
        parent._apply_button_state()

        new_content = _build_pending_content(
            parent.kind,
            parent.history_lines,
            parent._start_ts,
            parent._end_ts,
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

        # Open the 60s lock-decision window for the rigger. _open_lock_window
        # also cancels any prior lock window and edits the target message
        # with the countdown footer + Lock/Don't-Lock buttons.
        await parent._open_lock_window(user_id=interaction.user.id)

        await parent._release_concurrent_lock()
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
        await self._delete_self(interaction)
