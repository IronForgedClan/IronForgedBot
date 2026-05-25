import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from ironforgedbot.services.wom_service import (
    WomRateLimitError,
    WomServiceError,
    WomTimeoutError,
)
from tests.helpers import (
    VALID_CONFIG,
    create_mock_discord_interaction,
    create_test_db_member,
    create_test_member,
    mock_require_role,
)

with patch("ironforgedbot.decorators.require_role.require_role", mock_require_role):
    from ironforgedbot.commands.gains.cmd_gains import cmd_gains


def _make_snapshot(offset_days: int, value: int):
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return SimpleNamespace(date=base + timedelta(days=offset_days), value=value, rank=1)


def _make_snapshots(count: int = 10, xp_per_day: int = 10_000):
    """Return a list of snapshots with steady daily gains."""
    base_xp = 1_000_000
    return [_make_snapshot(i, base_xp + i * xp_per_day) for i in range(count)]


@patch.dict("os.environ", VALID_CONFIG)
class TestCmdGains(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=self.test_member)
        self.db_member = create_test_db_member(
            nickname="TestPlayer", rank="Iron", ingots=1000
        )

    def _make_wom_ctx(self, snapshots=None, raises=None):
        """Return a mock get_wom_service context manager."""
        mock_wom_svc = AsyncMock()
        if raises is not None:
            mock_wom_svc.get_player_snapshot_timeline.side_effect = raises
        else:
            mock_wom_svc.get_player_snapshot_timeline.return_value = (
                snapshots if snapshots is not None else _make_snapshots()
            )
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_wom_svc)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        return mock_ctx, mock_wom_svc

    def _setup_db(self, mock_db, mock_create_member_service, db_member=None):
        mock_session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_ctx

        mock_member_svc = AsyncMock()
        mock_member_svc.get_member_by_nickname.return_value = (
            db_member if db_member is not None else self.db_member
        )
        mock_create_member_service.return_value = mock_member_svc
        return mock_member_svc

    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_player_defaults_to_display_name(
        self, mock_find_emoji, mock_validate_playername
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.side_effect = ValueError("stop early")

        await cmd_gains(self.mock_interaction, None)

        mock_validate_playername.assert_called_once()
        args = mock_validate_playername.call_args
        self.assertEqual(args[0][1], self.test_member.display_name)

    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_validate_playername_raises_returns_error(
        self, mock_find_emoji, mock_validate_playername
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.side_effect = ValueError("bad name")

        await cmd_gains(self.mock_interaction, "???")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_player_not_in_guild_returns_error(
        self, mock_find_emoji, mock_validate_playername
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (None, "Ghost")

        await cmd_gains(self.mock_interaction, "Ghost")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.gains.cmd_gains.create_member_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.db")
    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_player_not_in_db_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")
        self._setup_db(mock_db, mock_create_member_service, db_member=None)

        await cmd_gains(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.gains.cmd_gains.get_wom_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.create_member_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.db")
    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_wom_rate_limit_error_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_get_wom_service,
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")
        self._setup_db(mock_db, mock_create_member_service)
        mock_ctx, _ = self._make_wom_ctx(raises=WomRateLimitError())
        mock_get_wom_service.return_value = mock_ctx

        await cmd_gains(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.gains.cmd_gains.get_wom_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.create_member_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.db")
    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_wom_timeout_error_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_get_wom_service,
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")
        self._setup_db(mock_db, mock_create_member_service)
        mock_ctx, _ = self._make_wom_ctx(raises=WomTimeoutError())
        mock_get_wom_service.return_value = mock_ctx

        await cmd_gains(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.gains.cmd_gains.get_wom_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.create_member_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.db")
    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_wom_service_error_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_get_wom_service,
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")
        self._setup_db(mock_db, mock_create_member_service)
        mock_ctx, _ = self._make_wom_ctx(raises=WomServiceError())
        mock_get_wom_service.return_value = mock_ctx

        await cmd_gains(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.gains.cmd_gains.get_wom_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.create_member_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.db")
    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_insufficient_snapshot_data_returns_error(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_get_wom_service,
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")
        self._setup_db(mock_db, mock_create_member_service)
        mock_ctx, _ = self._make_wom_ctx(snapshots=[_make_snapshot(0, 1_000_000)])
        mock_get_wom_service.return_value = mock_ctx

        await cmd_gains(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()

    @patch("ironforgedbot.commands.gains.cmd_gains.get_wom_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.create_member_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.db")
    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_success_sends_embed_with_required_fields(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_get_wom_service,
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")
        self._setup_db(mock_db, mock_create_member_service)
        mock_ctx, _ = self._make_wom_ctx(
            snapshots=_make_snapshots(10, xp_per_day=10_000)
        )
        mock_get_wom_service.return_value = mock_ctx

        await cmd_gains(self.mock_interaction, "TestPlayer")

        self.mock_interaction.followup.send.assert_called_once()
        embeds = self.mock_interaction.followup.send.call_args.kwargs["embeds"]
        embed = embeds[0]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "📈 Monthly Gains")

        field_names = [f.name for f in embed.fields]
        for expected in [
            "Member",
            "Period Start",
            "Period End",
            "Average",
            "Median",
        ]:
            self.assertIn(expected, field_names)

    @patch("ironforgedbot.commands.gains.cmd_gains.get_wom_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.create_member_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.db")
    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_success_total_in_gains_table(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_get_wom_service,
    ):
        """Gains table content contains the correct running total for the last row."""
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")
        self._setup_db(mock_db, mock_create_member_service)
        # 5 snapshots: days 0–4, each gaining 5k → running total by day 4 = 20,000
        # (day 0 has no predecessor so gain = 0)
        snapshots = _make_snapshots(5, xp_per_day=5_000)
        mock_ctx, _ = self._make_wom_ctx(snapshots=snapshots)
        mock_get_wom_service.return_value = mock_ctx

        await cmd_gains(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embeds"]
        self.assertIn("20,000", embed[1].description)

    @patch("ironforgedbot.commands.gains.cmd_gains.get_wom_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.create_member_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.db")
    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_success_embed_color_is_gold(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_get_wom_service,
    ):
        mock_find_emoji.return_value = ""
        mock_validate_playername.return_value = (self.test_member, "TestPlayer")
        self._setup_db(mock_db, mock_create_member_service)
        mock_ctx, _ = self._make_wom_ctx()
        mock_get_wom_service.return_value = mock_ctx

        await cmd_gains(self.mock_interaction, "TestPlayer")

        embed = self.mock_interaction.followup.send.call_args.kwargs["embeds"][0]
        self.assertEqual(embed.color, discord.Color.fuchsia())

    @patch("ironforgedbot.commands.gains.cmd_gains.get_wom_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.create_member_service")
    @patch("ironforgedbot.commands.gains.cmd_gains.db")
    @patch("ironforgedbot.commands.gains.cmd_gains.validate_playername")
    @patch("ironforgedbot.commands.gains.cmd_gains.find_emoji")
    async def test_explicit_player_arg_used(
        self,
        mock_find_emoji,
        mock_validate_playername,
        mock_db,
        mock_create_member_service,
        mock_get_wom_service,
    ):
        """When an explicit player name is given, validate_playername is called with it."""
        mock_find_emoji.return_value = ""
        mock_validate_playername.side_effect = ValueError("stop early")

        await cmd_gains(self.mock_interaction, "SomeOtherPlayer")

        args = mock_validate_playername.call_args
        self.assertEqual(args[0][1], "SomeOtherPlayer")


if __name__ == "__main__":
    unittest.main()
