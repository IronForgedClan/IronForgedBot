import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.commands.admin.spin_members_view import SpinMembersView


class TestSpinMembersView(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.view = SpinMembersView()
        self.interaction = Mock()
        self.interaction.response.defer = AsyncMock()
        self.role = Mock()
        self.role.name = "Iron"
        self.role.members = []
        self.select = Mock(values=[self.role])

    async def test_no_eligible_members_get_accurate_message(self):
        with patch(
            "ironforgedbot.commands.admin.spin_members_view.send_error_response",
            new_callable=AsyncMock,
        ) as send_error_response:
            await self.view.role_select.callback.callback(
                self.view, self.interaction, self.select
            )

        send_error_response.assert_awaited_once_with(
            self.interaction,
            "The role **Iron** has no eligible members to spin.",
        )

    async def test_single_eligible_member_can_spin(self):
        member = Mock(spec=discord.Member)
        member.bot = False
        member.display_name = "Solo"
        self.role.members = [member]
        file = Mock(spec=discord.File)

        with (
            patch(
                "ironforgedbot.commands.admin.spin_members_view.build_spin_gif_file",
                new_callable=AsyncMock,
                return_value=(file, "Solo"),
            ) as build_spin_gif_file,
            patch(
                "ironforgedbot.commands.admin.spin_members_view.send_spin_result",
                new_callable=AsyncMock,
            ) as send_spin_result,
        ):
            await self.view.role_select.callback.callback(
                self.view, self.interaction, self.select
            )

        build_spin_gif_file.assert_awaited_once_with(["Solo"])
        send_spin_result.assert_awaited_once_with(
            self.interaction,
            file,
            member.mention,
            spinning_text="_spinning everyone with the **Iron** role..._",
            winning_text="_and the winner is..._",
            emoji=None,
            use_padding=False,
            reactions=None,
        )
