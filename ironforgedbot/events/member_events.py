from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Set

import discord


@dataclass(frozen=True)
class MemberUpdateContext:
    """Context data passed to member update event handlers."""

    before: discord.Member
    after: discord.Member
    report_channel: discord.TextChannel
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def discord_id(self) -> int:
        """Discord ID of the member being updated."""
        return self.after.id

    @property
    def roles_added(self) -> Set[str]:
        """Set of role names that were added."""
        before_roles = {r.name for r in self.before.roles}
        after_roles = {r.name for r in self.after.roles}
        return after_roles - before_roles

    @property
    def roles_removed(self) -> Set[str]:
        """Set of role names that were removed."""
        before_roles = {r.name for r in self.before.roles}
        after_roles = {r.name for r in self.after.roles}
        return before_roles - after_roles

    @property
    def roles_changed(self) -> bool:
        """Whether any roles were added or removed."""
        return bool(self.roles_added or self.roles_removed)

    @property
    def nickname_changed(self) -> bool:
        """Whether the member's nickname changed."""
        return self.before.nick != self.after.nick


@dataclass
class HandlerResult:
    """Result from a handler execution."""

    handler_name: str
    success: bool
    duration_ms: float
    error: Optional[Exception] = None
