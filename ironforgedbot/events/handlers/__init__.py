"""Member update event handlers.

Importing this module triggers registration of all handlers with the
member_update_emitter. Handlers are sorted by priority and executed
in order when a member update event is emitted.
"""

# Import all handlers to trigger their self-registration
from ironforgedbot.events.handlers.add_member_role import AddMemberRoleHandler
from ironforgedbot.events.handlers.remove_member_role import RemoveMemberRoleHandler
from ironforgedbot.events.handlers.update_member_rank import UpdateMemberRankHandler
from ironforgedbot.events.handlers.update_member_role import UpdateMemberRoleHandler
from ironforgedbot.events.handlers.add_prospect_role import AddProspectRoleHandler
from ironforgedbot.events.handlers.remove_prospect_role import RemoveProspectRoleHandler
from ironforgedbot.events.handlers.nickname_change import NicknameChangeHandler
from ironforgedbot.events.handlers.add_banned_role import AddBannedRoleHandler
from ironforgedbot.events.handlers.remove_banned_role import RemoveBannedRoleHandler
from ironforgedbot.events.handlers.add_blacklisted_role import AddBlacklistedRoleHandler
from ironforgedbot.events.handlers.remove_blacklisted_role import (
    RemoveBlacklistedRoleHandler,
)
from ironforgedbot.events.handlers.add_booster_role import AddBoosterRoleHandler
from ironforgedbot.events.handlers.remove_booster_role import RemoveBoosterRoleHandler

__all__ = [
    "AddMemberRoleHandler",
    "RemoveMemberRoleHandler",
    "UpdateMemberRankHandler",
    "UpdateMemberRoleHandler",
    "AddProspectRoleHandler",
    "RemoveProspectRoleHandler",
    "NicknameChangeHandler",
    "AddBannedRoleHandler",
    "RemoveBannedRoleHandler",
    "AddBlacklistedRoleHandler",
    "RemoveBlacklistedRoleHandler",
    "AddBoosterRoleHandler",
    "RemoveBoosterRoleHandler",
]
