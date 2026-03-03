import unittest
from unittest.mock import Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
)


class TestParseOptions(unittest.TestCase):
    @patch("ironforgedbot.decorators.require_role.require_role", lambda r: lambda f: f)
    @patch(
        "ironforgedbot.decorators.command_price.command_price", lambda p: lambda f: f
    )
    def _import_parse_options(self):
        # Import with decorators mocked to avoid import-time side effects
        from ironforgedbot.commands.spin.cmd_spin import _parse_options

        return _parse_options

    def test_single_option_returns_none(self):
        _parse_options = self._import_parse_options()
        self.assertIsNone(_parse_options("only_one"))

    def test_spaces_trimmed(self):
        _parse_options = self._import_parse_options()
        self.assertEqual(
            _parse_options("  red  ,  blue  ,  green  "), ["red", "blue", "green"]
        )

    def test_commas_only_returns_none(self):
        _parse_options = self._import_parse_options()
        self.assertIsNone(_parse_options(",,,"))

    def test_valid_options(self):
        _parse_options = self._import_parse_options()
        self.assertEqual(_parse_options("a,b,c"), ["a", "b", "c"])

    def test_empty_string_returns_none(self):
        _parse_options = self._import_parse_options()
        self.assertIsNone(_parse_options(""))


@patch("ironforgedbot.decorators.require_role.require_role", lambda r: lambda f: f)
@patch("ironforgedbot.decorators.command_price.command_price", lambda p: lambda f: f)
class TestCmdSpin(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Import cmd_spin with decorators already mocked at class level
        from ironforgedbot.commands.spin.cmd_spin import cmd_spin

        self.cmd_spin = cmd_spin

        test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=test_member)

    @patch("ironforgedbot.commands.spin.cmd_spin.send_error_response")
    async def test_single_option_sends_error(self, mock_error):
        await self.cmd_spin(self.mock_interaction, options="only_one")
        mock_error.assert_called_once()
        self.mock_interaction.followup.send.assert_not_called()

    @patch("ironforgedbot.commands.spin.cmd_spin.build_spin_gif_file")
    async def test_valid_options_sends_file(self, mock_build):
        mock_file = Mock(spec=discord.File)
        mock_build.return_value = (mock_file, "red")

        await self.cmd_spin(self.mock_interaction, options="red,blue,green")

        mock_build.assert_called_once_with(["red", "blue", "green"])
        self.mock_interaction.followup.send.assert_called_once_with(file=mock_file)

    @patch("ironforgedbot.commands.spin.cmd_spin.send_error_response")
    @patch("ironforgedbot.commands.spin.cmd_spin.build_spin_gif_file")
    async def test_build_gif_exception_sends_error(self, mock_build, mock_error):
        mock_build.side_effect = Exception("test error")

        await self.cmd_spin(self.mock_interaction, options="red,blue,green")

        mock_error.assert_called_once()
        self.mock_interaction.followup.send.assert_not_called()

    @patch("ironforgedbot.commands.spin.cmd_spin.build_spin_gif_file")
    async def test_valid_options_no_embed(self, mock_build):
        mock_file = Mock(spec=discord.File)
        mock_build.return_value = (mock_file, "blue")

        await self.cmd_spin(self.mock_interaction, options="red,blue,green")

        call_kwargs = self.mock_interaction.followup.send.call_args.kwargs
        self.assertIn("file", call_kwargs)
        self.assertNotIn("embed", call_kwargs)
        self.assertNotIn("content", call_kwargs)
