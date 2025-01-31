import unittest
from unittest.mock import AsyncMock, patch

from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
    mock_score_breakdown,
)

with patch(
    "ironforgedbot.decorators.require_role",
    mock_require_role,
):
    from ironforgedbot.commands.hiscore.cmd_breakdown import cmd_breakdown


class BreakdownTest(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.score_info")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    async def test_cmd_breakdown(
        self,
        mock_validate_playername,
        mock_score_info,
    ):
        playername = "tester"
        user = create_test_member(playername, [ROLE.MEMBER])
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.return_value = (user, playername)
        mock_score_info.return_value = mock_score_breakdown

        with patch(
            "ironforgedbot.commands.hiscore.cmd_breakdown.ViewMenu"
        ) as mock_view_menu:
            mock_menu = mock_view_menu.return_value
            mock_menu.start = AsyncMock()

            await cmd_breakdown(interaction, playername)

            mock_menu.add_page.assert_called()
            mock_menu.add_button.assert_called()
            mock_menu.start.assert_called_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.score_info")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_prospect_response")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    async def test_cmd_breakdown_prospect_response(
        self,
        mock_validate_playername,
        mock_send_prospect_response,
        mock_score_info,
    ):
        playername = "tester"
        user = create_test_member(playername, [ROLE.PROSPECT])
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.return_value = (user, playername)
        mock_score_info.return_value = mock_score_breakdown

        await cmd_breakdown(interaction, playername)

        mock_send_prospect_response.assert_awaited_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.score_info")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_member_no_hiscore_values")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    async def test_cmd_breakdown_member_no_hiscore_response(
        self,
        mock_validate_playername,
        mock_send_no_hiscore_values,
        mock_score_info,
    ):
        playername = "tester"
        user = create_test_member(playername, [ROLE.MEMBER])
        interaction = create_mock_discord_interaction(user=user)

        mock_validate_playername.return_value = (user, playername)
        mock_score_info.return_value = None

        await cmd_breakdown(interaction, playername)

        mock_send_no_hiscore_values.assert_awaited_once()

    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.score_info")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.send_not_clan_member")
    @patch("ironforgedbot.commands.hiscore.cmd_breakdown.validate_playername")
    async def test_cmd_breakdown_not_in_clan_response(
        self,
        mock_validate_playername,
        mock_send_not_clan_member,
        mock_score_info,
    ):
        playername = "tester"
        interaction = create_mock_discord_interaction()

        mock_validate_playername.return_value = (None, playername)
        mock_score_info.return_value = mock_score_breakdown

        await cmd_breakdown(interaction, playername)

        mock_send_not_clan_member.assert_awaited_once()
