import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from reactionmenu import ViewButton, ViewMenu

from ironforgedbot.commands.leaderboard.leaderboard_menu import (
    LeaderboardMenu,
    build_leaderboard_menu,
)
from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    VALID_CONFIG,
    create_mock_discord_interaction,
    create_test_member,
)


@patch.dict("os.environ", VALID_CONFIG)
class TestLeaderboardMenuJumpToPage(unittest.IsolatedAsyncioTestCase):
    async def test_jump_to_page_sets_index_and_edits_message(self):
        mock_interaction = MagicMock()
        mock_interaction.response = AsyncMock()

        menu = LeaderboardMenu(mock_interaction, menu_type=ViewMenu.TypeEmbed)

        mock_pc = MagicMock()
        mock_pc.current_page = MagicMock()
        menu._pc = mock_pc

        mock_msg = AsyncMock()
        menu._msg = mock_msg

        menu._determine_kwargs = MagicMock(return_value={"content": "page content"})

        await menu.jump_to_page(3)

        self.assertEqual(mock_pc.index, 2)
        menu._determine_kwargs.assert_called_once_with(mock_pc.current_page)
        mock_msg.edit.assert_called_once_with(content="page content")

    async def test_jump_to_page_one_sets_index_zero(self):
        mock_interaction = MagicMock()
        mock_interaction.response = AsyncMock()

        menu = LeaderboardMenu(mock_interaction, menu_type=ViewMenu.TypeEmbed)

        mock_pc = MagicMock()
        mock_pc.current_page = MagicMock()
        menu._pc = mock_pc
        menu._msg = AsyncMock()
        menu._determine_kwargs = MagicMock(return_value={})

        await menu.jump_to_page(1)

        self.assertEqual(mock_pc.index, 0)


@patch.dict("os.environ", VALID_CONFIG)
class TestBuildLeaderboardMenu(unittest.TestCase):
    def _make_interaction(self):
        user = create_test_member("tester", [ROLE.MEMBER])
        return create_mock_discord_interaction(user=user)

    def _make_embeds(self, count: int = 1) -> list[discord.Embed]:
        return [
            discord.Embed(title=f"Page {i + 1}", description="test")
            for i in range(count)
        ]

    @patch("ironforgedbot.commands.leaderboard.leaderboard_menu.LeaderboardMenu")
    def test_find_me_button_added_when_caller_found(self, mock_menu_class):
        mock_menu = MagicMock()
        mock_menu_class.return_value = mock_menu

        interaction = self._make_interaction()
        embeds = self._make_embeds(2)

        build_leaderboard_menu(interaction, embeds, caller_page=2)

        button_calls = [str(call) for call in mock_menu.add_button.call_args_list]
        find_me_calls = [c for c in button_calls if "Find Me" in c]
        self.assertEqual(len(find_me_calls), 1)

    @patch("ironforgedbot.commands.leaderboard.leaderboard_menu.LeaderboardMenu")
    def test_find_me_button_omitted_when_caller_not_found(self, mock_menu_class):
        mock_menu = MagicMock()
        mock_menu_class.return_value = mock_menu

        interaction = self._make_interaction()
        embeds = self._make_embeds(2)

        build_leaderboard_menu(interaction, embeds, caller_page=None)

        button_calls = [str(call) for call in mock_menu.add_button.call_args_list]
        find_me_calls = [c for c in button_calls if "Find Me" in c]
        self.assertEqual(len(find_me_calls), 0)

    @patch("ironforgedbot.commands.leaderboard.leaderboard_menu.LeaderboardMenu")
    def test_nav_buttons_always_present(self, mock_menu_class):
        mock_menu = MagicMock()
        mock_menu_class.return_value = mock_menu

        interaction = self._make_interaction()
        embeds = self._make_embeds(1)

        build_leaderboard_menu(interaction, embeds, caller_page=None)

        button_calls = [str(call) for call in mock_menu.add_button.call_args_list]
        self.assertTrue(any("Back" in c for c in button_calls))
        self.assertTrue(any("Next" in c for c in button_calls))
        self.assertTrue(any("Close" in c for c in button_calls))

    @patch("ironforgedbot.commands.leaderboard.leaderboard_menu.LeaderboardMenu")
    def test_all_embeds_added_as_pages(self, mock_menu_class):
        mock_menu = MagicMock()
        mock_menu_class.return_value = mock_menu

        interaction = self._make_interaction()
        embeds = self._make_embeds(3)

        build_leaderboard_menu(interaction, embeds, caller_page=None)

        self.assertEqual(mock_menu.add_page.call_count, 3)

    @patch("ironforgedbot.commands.leaderboard.leaderboard_menu.LeaderboardMenu")
    def test_find_me_button_uses_id_caller(self, mock_menu_class):
        mock_menu = MagicMock()
        mock_menu_class.return_value = mock_menu

        interaction = self._make_interaction()
        embeds = self._make_embeds(2)

        build_leaderboard_menu(interaction, embeds, caller_page=2)

        added_buttons = [call.args[0] for call in mock_menu.add_button.call_args_list]
        find_me_button = next(b for b in added_buttons if b.label == "Find Me")
        self.assertTrue(find_me_button.custom_id.startswith(ViewButton.ID_CALLER))

    @patch("ironforgedbot.commands.leaderboard.leaderboard_menu.LeaderboardMenu")
    def test_find_me_button_has_followup_details(self, mock_menu_class):
        mock_menu = MagicMock()
        mock_menu_class.return_value = mock_menu

        interaction = self._make_interaction()
        embeds = self._make_embeds(2)

        build_leaderboard_menu(interaction, embeds, caller_page=2)

        added_buttons = [call.args[0] for call in mock_menu.add_button.call_args_list]
        find_me_button = next(b for b in added_buttons if b.label == "Find Me")
        self.assertIsNotNone(find_me_button.followup)
        self.assertIsNotNone(find_me_button.followup.details)


if __name__ == "__main__":
    unittest.main()
