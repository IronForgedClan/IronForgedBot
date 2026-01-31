import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

import discord

from ironforgedbot.events.member_events import HandlerResult, MemberUpdateContext
from tests.helpers import create_mock_discord_role, create_test_member


class TestMemberUpdateContext(unittest.TestCase):
    def setUp(self):
        self.before = create_test_member("TestUser", ["Member", "Iron"], "TestNick")
        self.after = create_test_member("TestUser", ["Member", "Iron"], "TestNick")
        self.after.id = self.before.id  # Ensure same discord ID
        self.report_channel = Mock(spec=discord.TextChannel)

    def test_discord_id_returns_after_id(self):
        """discord_id property returns the after member's ID."""
        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )
        self.assertEqual(context.discord_id, self.after.id)

    def test_roles_added_detects_new_roles(self):
        """roles_added returns set of roles added to after that weren't in before."""
        self.before.roles = [create_mock_discord_role("Member")]
        self.after.roles = [
            create_mock_discord_role("Member"),
            create_mock_discord_role("Iron"),
        ]

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertEqual(context.roles_added, {"Iron"})

    def test_roles_removed_detects_removed_roles(self):
        """roles_removed returns set of roles removed from before that aren't in after."""
        self.before.roles = [
            create_mock_discord_role("Member"),
            create_mock_discord_role("Iron"),
        ]
        self.after.roles = [create_mock_discord_role("Member")]

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertEqual(context.roles_removed, {"Iron"})

    def test_roles_added_empty_when_no_change(self):
        """roles_added returns empty set when no roles were added."""
        self.before.roles = [create_mock_discord_role("Member")]
        self.after.roles = [create_mock_discord_role("Member")]

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertEqual(context.roles_added, set())

    def test_roles_removed_empty_when_no_change(self):
        """roles_removed returns empty set when no roles were removed."""
        self.before.roles = [create_mock_discord_role("Member")]
        self.after.roles = [create_mock_discord_role("Member")]

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertEqual(context.roles_removed, set())

    def test_roles_changed_true_when_roles_added(self):
        """roles_changed returns True when roles were added."""
        self.before.roles = [create_mock_discord_role("Member")]
        self.after.roles = [
            create_mock_discord_role("Member"),
            create_mock_discord_role("Iron"),
        ]

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertTrue(context.roles_changed)

    def test_roles_changed_true_when_roles_removed(self):
        """roles_changed returns True when roles were removed."""
        self.before.roles = [
            create_mock_discord_role("Member"),
            create_mock_discord_role("Iron"),
        ]
        self.after.roles = [create_mock_discord_role("Member")]

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertTrue(context.roles_changed)

    def test_roles_changed_false_when_no_change(self):
        """roles_changed returns False when no roles were changed."""
        self.before.roles = [create_mock_discord_role("Member")]
        self.after.roles = [create_mock_discord_role("Member")]

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertFalse(context.roles_changed)

    def test_nickname_changed_true_when_nick_different(self):
        """nickname_changed returns True when nickname changed."""
        self.before.nick = "OldNick"
        self.after.nick = "NewNick"

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertTrue(context.nickname_changed)

    def test_nickname_changed_false_when_nick_same(self):
        """nickname_changed returns False when nickname unchanged."""
        self.before.nick = "SameNick"
        self.after.nick = "SameNick"

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertFalse(context.nickname_changed)

    def test_nickname_changed_handles_none_to_string(self):
        """nickname_changed handles None to string transition."""
        self.before.nick = None
        self.after.nick = "NewNick"

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertTrue(context.nickname_changed)

    def test_nickname_changed_handles_string_to_none(self):
        """nickname_changed handles string to None transition."""
        self.before.nick = "OldNick"
        self.after.nick = None

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertTrue(context.nickname_changed)

    def test_nickname_changed_handles_both_none(self):
        """nickname_changed returns False when both are None."""
        self.before.nick = None
        self.after.nick = None

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        self.assertFalse(context.nickname_changed)

    def test_default_timestamp(self):
        """Default timestamp is set to current UTC time."""
        before_creation = datetime.now(timezone.utc)

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        after_creation = datetime.now(timezone.utc)
        self.assertGreaterEqual(context.timestamp, before_creation)
        self.assertLessEqual(context.timestamp, after_creation)

    def test_custom_timestamp(self):
        """Custom timestamp can be provided."""
        custom_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
            timestamp=custom_time,
        )

        self.assertEqual(context.timestamp, custom_time)

    def test_frozen_dataclass_immutability(self):
        """MemberUpdateContext is frozen and cannot be modified."""
        context = MemberUpdateContext(
            before=self.before,
            after=self.after,
            report_channel=self.report_channel,
        )

        with self.assertRaises(AttributeError):
            context.before = self.after


class TestHandlerResult(unittest.TestCase):
    def test_creation_with_success(self):
        """HandlerResult can be created for successful execution."""
        result = HandlerResult(
            handler_name="TestHandler",
            success=True,
            duration_ms=5.5,
        )

        self.assertEqual(result.handler_name, "TestHandler")
        self.assertTrue(result.success)
        self.assertEqual(result.duration_ms, 5.5)
        self.assertIsNone(result.error)

    def test_creation_with_error(self):
        """HandlerResult can be created for failed execution with error."""
        error = ValueError("Test error")
        result = HandlerResult(
            handler_name="TestHandler",
            success=False,
            duration_ms=2.3,
            error=error,
        )

        self.assertEqual(result.handler_name, "TestHandler")
        self.assertFalse(result.success)
        self.assertEqual(result.duration_ms, 2.3)
        self.assertEqual(result.error, error)

    def test_default_error_is_none(self):
        """Default error is None when not provided."""
        result = HandlerResult(
            handler_name="TestHandler",
            success=True,
            duration_ms=1.0,
        )

        self.assertIsNone(result.error)
