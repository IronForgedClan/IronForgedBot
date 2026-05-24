import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.activity_check import ActivityCheckResult
from ironforgedbot.common.roles import ROLE
from ironforgedbot.services.wom_service import (
    WomRateLimitError,
    WomServiceError,
    WomTimeoutError,
)
from tests.helpers import (
    VALID_CONFIG,
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
    create_test_db_member,
)

with patch("ironforgedbot.decorators.require_role.require_role", mock_require_role):
    from ironforgedbot.commands.check.cmd_check import cmd_check


def _make_activity_result(
    username="TestPlayer",
    xp_gained=500000,
    xp_threshold=250000,
    is_active=True,
    is_exempt=False,
    is_absent=False,
    is_prospect=False,
    skip_reason=None,
) -> ActivityCheckResult:
    return ActivityCheckResult(
        username=username,
        wom_role=None,
        discord_role=None,
        xp_gained=xp_gained,
        xp_threshold=xp_threshold,
        is_active=is_active,
        is_exempt=is_exempt,
        is_absent=is_absent,
        is_prospect=is_prospect,
        last_changed_at=None,
        check_timestamp=datetime.now(timezone.utc),
        skip_reason=skip_reason,
    )


def _make_player_gains_mock(overall_xp: float = 1_000_000.0):
    from wom import Metric

    overall_mock = Mock()
    overall_mock.experience.gained = overall_xp

    skills_mock = {Metric.Overall: overall_mock}

    data_mock = Mock()
    data_mock.skills = skills_mock

    gains_mock = Mock()
    gains_mock.data = data_mock

    return gains_mock


@patch.dict("os.environ", VALID_CONFIG)
class TestCmdCheck(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=self.test_member)
        self.db_member = create_test_db_member(
            nickname="TestPlayer", rank="Iron", ingots=1000
        )

    def _make_wom_mocks(self, player_gains=None):
        """Return (mock_get_wom_service, mock_wom_service) with sensible defaults."""
        if player_gains is None:
            player_gains = _make_player_gains_mock()

        mock_wom_service = AsyncMock()
        mock_wom_service.get_player_monthly_gains.return_value = player_gains
        mock_wom_service.get_group_membership_data.return_value = Mock()
        mock_wom_service.get_player_snapshot_timeline.return_value = []

        mock_get_wom = Mock()
        mock_get_wom.return_value.__aenter__ = AsyncMock(return_value=mock_wom_service)
        mock_get_wom.return_value.__aexit__ = AsyncMock(return_value=None)
        return mock_get_wom, mock_wom_service

    def _setup_common(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
    ):
        """Wire up the standard happy-path mocks shared across most tests."""
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_ctx

        mock_member_svc = AsyncMock()
        mock_member_svc.get_member_by_nickname.return_value = self.db_member
        mock_create_member_service.return_value = mock_member_svc

        mock_absent_svc = AsyncMock()
        mock_absent_svc.process_absent_members.return_value = []
        mock_create_absent_service.return_value = mock_absent_svc

        mock_get_wom, mock_wom_svc = self._make_wom_mocks()
        mock_get_wom_service.return_value = mock_get_wom.return_value

        return mock_wom_svc

    def _setup_ltm_wom(self, mock_wom_service_cls, overall_xp=500_000.0, raises=False):
        """Configure the LTM WomService context manager mock."""
        mock_ltm_svc = AsyncMock()
        if raises:
            mock_ltm_svc.get_player_monthly_gains.side_effect = Exception("LTM down")
        else:
            mock_ltm_svc.get_player_monthly_gains.return_value = (
                _make_player_gains_mock(overall_xp=overall_xp)
            )
        mock_ltm_instance = AsyncMock()
        mock_ltm_instance.__aenter__ = AsyncMock(return_value=mock_ltm_svc)
        mock_ltm_instance.__aexit__ = AsyncMock(return_value=None)
        mock_wom_service_cls.return_value = mock_ltm_instance
        return mock_ltm_svc

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_validate_playername_raises_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_config,
    ):
        """If validate_playername raises, an error response is sent."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        mock_find_emoji.return_value = ""
        mock_validate_playername.side_effect = ValueError("bad name")

        await cmd_check(self.mock_interaction, "???")

        self.mock_interaction.followup.send.assert_called_once()
        call_kwargs = self.mock_interaction.followup.send.call_args.kwargs
        self.assertIn("embed", call_kwargs)

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_member_not_on_server_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_config,
    ):
        """If validate_playername returns None member, an error response is sent."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (None, "Ghost")

        await cmd_check(self.mock_interaction, "Ghost")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_member_not_in_db_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_config,
    ):
        """If the DB lookup returns None, an error response is sent."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_ctx

        mock_member_svc = AsyncMock()
        mock_member_svc.get_member_by_nickname.return_value = None
        mock_create_member_service.return_value = mock_member_svc

        await cmd_check(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_wom_rate_limit_error_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_config,
    ):
        """WomRateLimitError from WOM fetch returns an error response."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_ctx

        mock_member_svc = AsyncMock()
        mock_member_svc.get_member_by_nickname.return_value = self.db_member
        mock_create_member_service.return_value = mock_member_svc

        mock_absent_svc = AsyncMock()
        mock_absent_svc.process_absent_members.return_value = []
        mock_create_absent_service.return_value = mock_absent_svc

        mock_wom_svc = AsyncMock()
        mock_wom_svc.get_player_monthly_gains.side_effect = WomRateLimitError()
        mock_ctx_wom = AsyncMock()
        mock_ctx_wom.__aenter__ = AsyncMock(return_value=mock_wom_svc)
        mock_ctx_wom.__aexit__ = AsyncMock(return_value=None)
        mock_get_wom_service.return_value = mock_ctx_wom

        await cmd_check(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_wom_timeout_error_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_config,
    ):
        """WomTimeoutError from WOM fetch returns an error response."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_ctx

        mock_member_svc = AsyncMock()
        mock_member_svc.get_member_by_nickname.return_value = self.db_member
        mock_create_member_service.return_value = mock_member_svc

        mock_absent_svc = AsyncMock()
        mock_absent_svc.process_absent_members.return_value = []
        mock_create_absent_service.return_value = mock_absent_svc

        mock_wom_svc = AsyncMock()
        mock_wom_svc.get_player_monthly_gains.side_effect = WomTimeoutError()
        mock_ctx_wom = AsyncMock()
        mock_ctx_wom.__aenter__ = AsyncMock(return_value=mock_wom_svc)
        mock_ctx_wom.__aexit__ = AsyncMock(return_value=None)
        mock_get_wom_service.return_value = mock_ctx_wom

        await cmd_check(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_wom_service_error_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_config,
    ):
        """WomServiceError from WOM fetch returns an error response."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")

        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_ctx

        mock_member_svc = AsyncMock()
        mock_member_svc.get_member_by_nickname.return_value = self.db_member
        mock_create_member_service.return_value = mock_member_svc

        mock_absent_svc = AsyncMock()
        mock_absent_svc.process_absent_members.return_value = []
        mock_create_absent_service.return_value = mock_absent_svc

        mock_wom_svc = AsyncMock()
        mock_wom_svc.get_player_monthly_gains.side_effect = WomServiceError()
        mock_ctx_wom = AsyncMock()
        mock_ctx_wom.__aenter__ = AsyncMock(return_value=mock_wom_svc)
        mock_ctx_wom.__aexit__ = AsyncMock(return_value=None)
        mock_get_wom_service.return_value = mock_ctx_wom

        await cmd_check(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_check_member_activity_raises_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
    ):
        """If check_member_activity raises, an error response is sent."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        mock_check_member_activity.side_effect = Exception("activity boom")

        await cmd_check(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_not_in_group_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
    ):
        """skip_reason == 'not_in_group' returns an error response."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        mock_check_member_activity.return_value = _make_activity_result(
            skip_reason="not_in_group"
        )

        await cmd_check(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_player_defaults_to_display_name(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_config,
    ):
        """When player=None, the command uses the caller's display_name."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        mock_find_emoji.return_value = ""
        mock_validate_playername.side_effect = ValueError("stop early")

        await cmd_check(self.mock_interaction, None)

        mock_validate_playername.assert_called_once()
        args = mock_validate_playername.call_args
        self.assertEqual(args[0][1], self.test_member.display_name)

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_active_member_shows_safe_green(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
    ):
        """An active member shows '✅ Safe' with a green embed and no Note field."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        mock_check_member_activity.return_value = _make_activity_result(is_active=True)

        await cmd_check(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]
        status_field = next(f for f in embed.fields if f.name == "Status")
        self.assertEqual(status_field.value, "✅ Safe")
        self.assertEqual(embed.color, discord.Colour.green())
        note_fields = [f for f in embed.fields if f.name == "Notes"]
        self.assertEqual(len(note_fields), 0)

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_exempt_member_shows_safe_green(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
    ):
        """An exempt member shows '✅ Safe' with a green embed and exempt note."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        mock_check_member_activity.return_value = _make_activity_result(
            is_active=False, is_exempt=True
        )

        await cmd_check(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]
        status_field = next(f for f in embed.fields if f.name == "Status")
        self.assertEqual(status_field.value, "✅ Safe")
        self.assertEqual(embed.color, discord.Colour.green())
        note_fields = [f for f in embed.fields if f.name == "Notes"]
        self.assertEqual(len(note_fields), 1)
        self.assertIn("exempts them from activity checks", note_fields[0].value)

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_prospect_member_shows_safe_green(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
    ):
        """A prospect member shows '✅ Safe' with a green embed and prospect note."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        mock_check_member_activity.return_value = _make_activity_result(
            is_active=False, is_prospect=True
        )

        await cmd_check(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]
        status_field = next(f for f in embed.fields if f.name == "Status")
        self.assertEqual(status_field.value, "✅ Safe")
        self.assertEqual(embed.color, discord.Colour.green())
        note_fields = [f for f in embed.fields if f.name == "Notes"]
        self.assertEqual(len(note_fields), 1)
        self.assertIn("Prospect", note_fields[0].value)

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_ltm_disabled_no_ltm_field(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
    ):
        """When LTM is disabled the embed should not have an LTM Gained field and no LTM note."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        mock_check_member_activity.return_value = _make_activity_result()

        await cmd_check(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()
        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]

        field_names = [f.name for f in embed.fields]
        self.assertNotIn("LTM Gained", field_names)
        note_fields = [f for f in embed.fields if f.name == "Notes"]
        for nf in note_fields:
            self.assertNotIn("LTM (Limited Time Mode)", nf.value)

    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_ltm_disabled_inactive_in_danger(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
    ):
        """With LTM disabled, an inactive member always shows 'In danger' and red embed."""
        mock_config.ltm_enabled = False
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        mock_check_member_activity.return_value = _make_activity_result(
            is_active=False, xp_gained=0
        )

        await cmd_check(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]
        status_field = next(f for f in embed.fields if f.name == "Status")
        self.assertEqual(status_field.value, "❌ In danger")
        self.assertEqual(embed.color, discord.Colour.red())

    @patch("ironforgedbot.commands.check.cmd_check.WomService")
    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_ltm_enabled_shows_ltm_xp_and_note(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
        mock_wom_service_cls,
    ):
        """When LTM is enabled and fetch succeeds, embed shows LTM xp and note."""
        mock_config.ltm_enabled = True
        mock_config.WOM_LTM_BASE_URL = "https://ltm.example.com"
        mock_config.WOM_LTM_GROUP_ID = 9999
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        self._setup_ltm_wom(mock_wom_service_cls, overall_xp=1_234_567.0)
        mock_check_member_activity.return_value = _make_activity_result()

        await cmd_check(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()
        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]

        field_names = [f.name for f in embed.fields]
        self.assertIn("LTM Gained", field_names)

        ltm_field = next(f for f in embed.fields if f.name == "LTM Gained")
        self.assertEqual(ltm_field.value, "1,234,567 xp")
        self.assertTrue(ltm_field.inline)

        note_fields = [f for f in embed.fields if f.name == "Notes"]
        self.assertEqual(len(note_fields), 1)
        self.assertIn("LTM (Limited Time Mode)", note_fields[0].value)

    @patch("ironforgedbot.commands.check.cmd_check.WomService")
    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_ltm_enabled_fetch_fails_shows_na(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
        mock_wom_service_cls,
    ):
        """When LTM is enabled but the fetch fails, the LTM Gained field shows N/A."""
        mock_config.ltm_enabled = True
        mock_config.WOM_LTM_BASE_URL = "https://ltm.example.com"
        mock_config.WOM_LTM_GROUP_ID = 9999
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        self._setup_ltm_wom(mock_wom_service_cls, raises=True)
        mock_check_member_activity.return_value = _make_activity_result()

        await cmd_check(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()
        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]

        field_names = [f.name for f in embed.fields]
        self.assertIn("LTM Gained", field_names)

        ltm_field = next(f for f in embed.fields if f.name == "LTM Gained")
        self.assertEqual(ltm_field.value, "N/A")

        note_fields = [f for f in embed.fields if f.name == "Notes"]
        self.assertEqual(len(note_fields), 1)
        self.assertIn("LTM (Limited Time Mode)", note_fields[0].value)

    @patch("ironforgedbot.commands.check.cmd_check.WomService")
    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_ltm_note_appended_to_existing_note(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
        mock_wom_service_cls,
    ):
        """Absent+inactive member with positive LTM gains gets both the absent note and LTM note."""
        mock_config.ltm_enabled = True
        mock_config.WOM_LTM_BASE_URL = "https://ltm.example.com"
        mock_config.WOM_LTM_GROUP_ID = 9999
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        self._setup_ltm_wom(mock_wom_service_cls, overall_xp=500_000.0)
        mock_check_member_activity.return_value = _make_activity_result(
            is_absent=True, is_active=False
        )

        await cmd_check(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]
        note_fields = [f for f in embed.fields if f.name == "Notes"]
        self.assertEqual(len(note_fields), 1)
        note_value = note_fields[0].value
        self.assertIn("LTM (Limited Time Mode)", note_value)
        self.assertIn("marked as absent", note_value)
        self.assertIn("has not met the main game activity requirement", note_value)
        self.assertTrue(note_value.startswith("LTM (Limited Time Mode)"))
        self.assertIn("\n\n", note_value)

    @patch("ironforgedbot.commands.check.cmd_check.WomService")
    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_ltm_inactive_positive_gains_leadership_discretion(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
        mock_wom_service_cls,
    ):
        """Inactive member with positive LTM gains shows leadership discretion status and orange embed."""
        mock_config.ltm_enabled = True
        mock_config.WOM_LTM_BASE_URL = "https://ltm.example.com"
        mock_config.WOM_LTM_GROUP_ID = 9999
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        self._setup_ltm_wom(mock_wom_service_cls, overall_xp=500_000.0)
        mock_check_member_activity.return_value = _make_activity_result(
            is_active=False, xp_gained=0
        )

        await cmd_check(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]
        status_field = next(f for f in embed.fields if f.name == "Status")
        self.assertEqual(status_field.value, "🟠 Pending review")
        self.assertEqual(embed.color, discord.Colour.orange())

        note_fields = [f for f in embed.fields if f.name == "Notes"]
        self.assertEqual(len(note_fields), 1)
        note_value = note_fields[0].value
        self.assertTrue(note_value.startswith("LTM (Limited Time Mode)"))
        self.assertIn("has not met the main game activity requirement", note_value)
        self.assertIn("LTM gains", note_value)
        self.assertIn("reviewed by leadership", note_value)
        self.assertIn("\n\n", note_value)

    @patch("ironforgedbot.commands.check.cmd_check.WomService")
    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_ltm_inactive_zero_gains_in_danger(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
        mock_wom_service_cls,
    ):
        """Inactive member with zero LTM gains keeps 'In danger' status and red embed."""
        mock_config.ltm_enabled = True
        mock_config.WOM_LTM_BASE_URL = "https://ltm.example.com"
        mock_config.WOM_LTM_GROUP_ID = 9999
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        self._setup_ltm_wom(mock_wom_service_cls, overall_xp=0.0)
        mock_check_member_activity.return_value = _make_activity_result(
            is_active=False, xp_gained=0
        )

        await cmd_check(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]
        status_field = next(f for f in embed.fields if f.name == "Status")
        self.assertEqual(status_field.value, "❌ In danger")
        self.assertEqual(embed.color, discord.Colour.red())

        note_fields = [f for f in embed.fields if f.name == "Notes"]
        self.assertEqual(len(note_fields), 1)
        self.assertIn("LTM (Limited Time Mode)", note_fields[0].value)

    @patch("ironforgedbot.commands.check.cmd_check.WomService")
    @patch("ironforgedbot.commands.check.cmd_check.CONFIG")
    @patch("ironforgedbot.commands.check.cmd_check.check_member_activity")
    @patch("ironforgedbot.commands.check.cmd_check.get_wom_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_absent_service")
    @patch("ironforgedbot.commands.check.cmd_check.create_member_service")
    @patch("ironforgedbot.commands.check.cmd_check.db")
    @patch("ironforgedbot.commands.check.cmd_check.validate_playername")
    @patch("ironforgedbot.commands.check.cmd_check.find_emoji")
    async def test_ltm_inactive_fetch_failed_in_danger(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_create_absent_service,
        mock_get_wom_service,
        mock_check_member_activity,
        mock_config,
        mock_wom_service_cls,
    ):
        """Inactive member whose LTM fetch failed keeps 'In danger' status and red embed."""
        mock_config.ltm_enabled = True
        mock_config.WOM_LTM_BASE_URL = "https://ltm.example.com"
        mock_config.WOM_LTM_GROUP_ID = 9999
        mock_config.RULES_CHANNEL_ID = 123456
        self._setup_common(
            mock_find_emoji,
            mock_validate_playername,
            mock_db,
            mock_create_member_service,
            mock_create_absent_service,
            mock_get_wom_service,
        )
        self._setup_ltm_wom(mock_wom_service_cls, raises=True)
        mock_check_member_activity.return_value = _make_activity_result(
            is_active=False, xp_gained=0
        )

        await cmd_check(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embed"]
        status_field = next(f for f in embed.fields if f.name == "Status")
        self.assertEqual(status_field.value, "❌ In danger")
        self.assertEqual(embed.color, discord.Colour.red())

        note_fields = [f for f in embed.fields if f.name == "Notes"]
        self.assertEqual(len(note_fields), 1)
        self.assertIn("LTM (Limited Time Mode)", note_fields[0].value)


if __name__ == "__main__":
    unittest.main()
