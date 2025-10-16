import unittest
from unittest.mock import Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    mock_require_role,
    create_mock_discord_interaction,
    create_test_member,
)

with patch("ironforgedbot.decorators.require_role", mock_require_role):
    from ironforgedbot.commands.rng_reset.cmd_rng_reset import cmd_rng_reset


class TestCmdRngReset(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=test_member)

    @patch("ironforgedbot.commands.rng_reset.cmd_rng_reset.random.random")
    @patch("ironforgedbot.commands.rng_reset.cmd_rng_reset.build_response_embed")
    async def test_cmd_rng_reset_success(self, mock_build_embed, mock_random):
        mock_random.return_value = 0.3

        mock_embed = Mock()
        mock_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = mock_embed

        await cmd_rng_reset(self.mock_interaction)

        mock_build_embed.assert_called_once_with(
            title="RNG Reset Successful!",
            description="Your RNG has been restored. That pet is definitely dropping on your next kill. Probably.",
            color=discord.Colour.green(),
        )
        mock_embed.set_thumbnail.assert_called_once_with(
            url="https://oldschool.runescape.wiki/images/thumb/Reward_casket_%28master%29.png/150px-Reward_casket_%28master%29.png"
        )
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.commands.rng_reset.cmd_rng_reset.random.random")
    @patch("ironforgedbot.commands.rng_reset.cmd_rng_reset.build_response_embed")
    async def test_cmd_rng_reset_failure(self, mock_build_embed, mock_random):
        mock_random.return_value = 0.7

        mock_embed = Mock()
        mock_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = mock_embed

        await cmd_rng_reset(self.mock_interaction)

        mock_build_embed.assert_called_once_with(
            title="You rolled a 0!",
            description="The RNG gods have denied your request. Enjoy staying dry for another 10,000 kills.",
            color=discord.Colour.red(),
        )
        mock_embed.set_thumbnail.assert_called_once_with(
            url="https://oldschool.runescape.wiki/images/thumb/Skull.png/130px-Skull.png"
        )
        self.mock_interaction.followup.send.assert_called_once_with(embed=mock_embed)

    @patch("ironforgedbot.commands.rng_reset.cmd_rng_reset.random.random")
    @patch("ironforgedbot.commands.rng_reset.cmd_rng_reset.build_response_embed")
    async def test_cmd_rng_reset_boundary_success(self, mock_build_embed, mock_random):
        mock_random.return_value = 0.49999

        mock_embed = Mock()
        mock_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = mock_embed

        await cmd_rng_reset(self.mock_interaction)

        mock_build_embed.assert_called_once_with(
            title="RNG Reset Successful!",
            description="Your RNG has been restored. That pet is definitely dropping on your next kill. Probably.",
            color=discord.Colour.green(),
        )

    @patch("ironforgedbot.commands.rng_reset.cmd_rng_reset.random.random")
    @patch("ironforgedbot.commands.rng_reset.cmd_rng_reset.build_response_embed")
    async def test_cmd_rng_reset_boundary_failure(self, mock_build_embed, mock_random):
        mock_random.return_value = 0.5

        mock_embed = Mock()
        mock_embed.set_thumbnail = Mock()
        mock_build_embed.return_value = mock_embed

        await cmd_rng_reset(self.mock_interaction)

        mock_build_embed.assert_called_once_with(
            title="You rolled a 0!",
            description="The RNG gods have denied your request. Enjoy staying dry for another 10,000 kills.",
            color=discord.Colour.red(),
        )
