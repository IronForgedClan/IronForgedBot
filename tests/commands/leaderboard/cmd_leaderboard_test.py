import functools
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from ironforgedbot.commands.leaderboard.leaderboard_types import (
    LEADERBOARD_TYPES,
    LeaderboardEntry,
)
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    VALID_CONFIG,
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
)


def mock_log_command_execution(*_args, **_kwargs):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


with patch(
    "ironforgedbot.decorators.require_role.require_role", mock_require_role
), patch(
    "ironforgedbot.common.logging_utils.log_command_execution",
    mock_log_command_execution,
):
    from ironforgedbot.commands.leaderboard.cmd_leaderboard import cmd_leaderboard


def _make_entry(
    nickname: str = "Player",
    value: int = 1000,
    discord_id: int = 12345,
) -> LeaderboardEntry:
    return LeaderboardEntry(discord_id=discord_id, nickname=nickname, value=value)


def _make_choice(value: str = "ingots") -> MagicMock:
    choice = MagicMock()
    choice.value = value
    return choice


@patch.dict("os.environ", VALID_CONFIG)
class TestCmdLeaderboard(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_user = create_test_member("Caller", [ROLE.MEMBER])
        self.test_user.id = 42
        self.interaction = create_mock_discord_interaction(user=self.test_user)

    def _make_entries(
        self, count: int, caller_discord_id: int | None = None
    ) -> list[LeaderboardEntry]:
        entries = []
        for i in range(count):
            discord_id = caller_discord_id if i == count // 2 else (i + 1000)
            entries.append(
                _make_entry(
                    nickname=f"Player{i}",
                    value=10000 - (i * 100),
                    discord_id=discord_id,
                )
            )
        return entries

    async def _run_cmd(
        self, entries: list[LeaderboardEntry], choice_value: str = "ingots"
    ):
        mock_fetcher = AsyncMock(return_value=entries)
        mock_menu = AsyncMock()

        with patch.object(
            LEADERBOARD_TYPES[choice_value], "fetcher", mock_fetcher
        ), patch(
            "ironforgedbot.commands.leaderboard.leaderboard_menu.LeaderboardMenu",
            return_value=mock_menu,
        ), patch(
            "ironforgedbot.commands.leaderboard.cmd_leaderboard.db"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_ctx

            await cmd_leaderboard(self.interaction, _make_choice(choice_value))

        return mock_fetcher, mock_menu

    async def test_happy_path_ingots(self):
        entries = self._make_entries(10)
        mock_fetcher, mock_menu = await self._run_cmd(entries, "ingots")

        mock_fetcher.assert_called_once()
        mock_menu.start.assert_called_once()

    async def test_happy_path_score(self):
        entries = self._make_entries(10)
        mock_fetcher, mock_menu = await self._run_cmd(entries, "score")

        mock_fetcher.assert_called_once()
        mock_menu.start.assert_called_once()

    async def test_entries_sorted_descending(self):
        entries = [
            _make_entry(nickname="Low", value=100, discord_id=1),
            _make_entry(nickname="High", value=9999, discord_id=2),
            _make_entry(nickname="Mid", value=5000, discord_id=3),
        ]
        captured_embeds: list[discord.Embed] = []

        mock_fetcher = AsyncMock(return_value=entries)
        mock_menu = MagicMock()
        mock_menu.start = AsyncMock()
        mock_menu.add_page.side_effect = lambda embed: captured_embeds.append(embed)

        with patch.object(LEADERBOARD_TYPES["ingots"], "fetcher", mock_fetcher), patch(
            "ironforgedbot.commands.leaderboard.leaderboard_menu.LeaderboardMenu",
            return_value=mock_menu,
        ), patch("ironforgedbot.commands.leaderboard.cmd_leaderboard.db") as mock_db:
            mock_session = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_ctx

            await cmd_leaderboard(self.interaction, _make_choice("ingots"))

        self.assertEqual(len(captured_embeds), 1)
        desc = captured_embeds[0].description
        high_pos = desc.index("| High ")
        mid_pos = desc.index("| Mid ")
        low_pos = desc.index("| Low ")
        self.assertLess(high_pos, mid_pos)
        self.assertLess(mid_pos, low_pos)

    async def test_find_me_button_added_when_caller_in_list(self):
        entries = [
            _make_entry(nickname="Other", value=9999, discord_id=999),
            _make_entry(nickname="Caller", value=500, discord_id=self.test_user.id),
        ]
        _, mock_menu = await self._run_cmd(entries)

        button_calls = [str(call) for call in mock_menu.add_button.call_args_list]
        self.assertEqual(len([c for c in button_calls if "Find Me" in c]), 1)

    async def test_find_me_button_absent_when_caller_not_in_list(self):
        entries = [
            _make_entry(nickname="Other1", value=9999, discord_id=111),
            _make_entry(nickname="Other2", value=5000, discord_id=222),
        ]
        _, mock_menu = await self._run_cmd(entries)

        button_calls = [str(call) for call in mock_menu.add_button.call_args_list]
        self.assertEqual(len([c for c in button_calls if "Find Me" in c]), 0)

    async def test_empty_entry_list(self):
        _, mock_menu = await self._run_cmd([])

        mock_menu.start.assert_called_once()
        captured = [call.args[0] for call in mock_menu.add_page.call_args_list]
        self.assertEqual(len(captured), 1)
        self.assertIn("No members found", captured[0].description)

    async def test_menu_start_error_sends_error_response(self):
        entries = [_make_entry(nickname="Player", value=500, discord_id=999)]
        mock_fetcher = AsyncMock(return_value=entries)
        mock_menu = AsyncMock()
        mock_menu.start.side_effect = Exception("menu failure")

        with patch.object(LEADERBOARD_TYPES["ingots"], "fetcher", mock_fetcher), patch(
            "ironforgedbot.commands.leaderboard.leaderboard_menu.LeaderboardMenu",
            return_value=mock_menu,
        ), patch(
            "ironforgedbot.commands.leaderboard.cmd_leaderboard.db"
        ) as mock_db, patch(
            "ironforgedbot.commands.leaderboard.cmd_leaderboard.send_error_response"
        ) as mock_send_error:
            mock_session = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.get_session.return_value = mock_ctx

            await cmd_leaderboard(self.interaction, _make_choice("ingots"))

        mock_send_error.assert_called_once()
        mock_menu.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
