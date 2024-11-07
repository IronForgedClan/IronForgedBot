import unittest
from unittest.mock import AsyncMock, patch

import discord
from tabulate import tabulate

from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
    validate_embed,
)

with patch(
    "ironforgedbot.decorators.require_role",
    mock_require_role,
):
    from ironforgedbot.commands.ingots.cmd_add_remove_ingots import (
        cmd_add_remove_ingots,
    )


class TestAddRemoveIngots(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_remove_ingots.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_add_remove_ingots_one_target(
        self, mock_storage, mock_validate_playername
    ):
        """Test that ingots can be added to a single user."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        target = create_test_member("tester", ROLES.MEMBER)
        reason = "testing"

        interaction = create_mock_discord_interaction(user=caller, members=[target])

        mock_storage.read_members.return_value = [
            Member(id=target.id, runescape_name=target.display_name, ingots=5000)
        ]
        mock_validate_playername.return_value = target, target.display_name

        await cmd_add_remove_ingots(interaction, target.display_name, 5000, reason)

        mock_storage.update_members.assert_called_once_with(
            [Member(id=target.id, runescape_name=target.display_name, ingots=10000)],
            caller.display_name,
            note=reason,
        )

        actual_embed = interaction.followup.send.call_args.kwargs["embed"]

        expected_embed = discord.Embed(
            title=" Add Ingots Result",
            description=(f"**Total Change:** +5,000\n" f"**Reason:** _{reason}_"),
        )
        expected_result_table = tabulate(
            [[target.display_name, "+5,000", "10,000"]],
            headers=["Player", "Change", "Total"],
            tablefmt="github",
        )
        expected_embed.add_field(name="", value=f"```{expected_result_table}```")

        interaction.followup.send.assert_called_once()
        validate_embed(self, expected_embed, actual_embed)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_remove_ingots.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_add_remove_ingots_one_target_remove(
        self, mock_storage, mock_validate_playername
    ):
        """Test that ingots can be removed from a single user."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        target = create_test_member("tester", ROLES.MEMBER)
        reason = "testing"

        interaction = create_mock_discord_interaction(user=caller, members=[target])

        mock_storage.read_members.return_value = [
            Member(id=target.id, runescape_name=target.display_name, ingots=5000)
        ]
        mock_validate_playername.return_value = target, target.display_name

        await cmd_add_remove_ingots(interaction, target.display_name, -2000, reason)

        mock_storage.update_members.assert_called_once_with(
            [Member(id=target.id, runescape_name=target.display_name, ingots=3000)],
            caller.display_name,
            note=reason,
        )

        actual_embed = interaction.followup.send.call_args.kwargs["embed"]

        expected_embed = discord.Embed(
            title=" Remove Ingots Result",
            description=(f"**Total Change:** -2,000\n" f"**Reason:** _{reason}_"),
        )
        expected_result_table = tabulate(
            [[target.display_name, "-2,000", "3,000"]],
            headers=["Player", "Change", "Total"],
            tablefmt="github",
        )
        expected_embed.add_field(name="", value=f"```{expected_result_table}```")

        interaction.followup.send.assert_called_once()
        validate_embed(self, expected_embed, actual_embed)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_remove_ingots.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_add_remove_ingots_multiple_targets(
        self, mock_storage, mock_validate_playername
    ):
        """Test that ingots can be added to multiple users at once."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        target1 = create_test_member("atester", ROLES.MEMBER)
        target2 = create_test_member("btester", ROLES.MEMBER)
        target3 = create_test_member("ctester", ROLES.MEMBER)
        reason = "testing"

        interaction = create_mock_discord_interaction(
            user=caller, members=[target1, target2, target3]
        )

        mock_storage.read_members.return_value = [
            Member(id=target1.id, runescape_name=target1.display_name, ingots=5000),
            Member(id=target2.id, runescape_name=target2.display_name, ingots=10000),
            Member(id=target3.id, runescape_name=target3.display_name, ingots=125000),
        ]

        mock_validate_playername.side_effect = lambda _, name: (
            None,
            name,
        )

        await cmd_add_remove_ingots(
            interaction,
            f"{target1.display_name},{target2.display_name},{target3.display_name}",
            5000,
            reason,
        )

        mock_storage.update_members.assert_called_once_with(
            [
                Member(
                    id=target1.id, runescape_name=target1.display_name, ingots=10000
                ),
                Member(
                    id=target2.id, runescape_name=target2.display_name, ingots=15000
                ),
                Member(
                    id=target3.id, runescape_name=target3.display_name, ingots=130000
                ),
            ],
            caller.display_name,
            note=reason,
        )

        actual_embed = interaction.followup.send.call_args.kwargs["embed"]

        expected_embed = discord.Embed(
            title=" Add Ingots Result",
            description=(f"**Total Change:** +5,000\n" f"**Reason:** _{reason}_"),
        )
        expected_result_table = tabulate(
            [
                [target1.display_name, "+5,000", "10,000"],
                [target2.display_name, "+5,000", "15,000"],
                [target3.display_name, "+5,000", "130,000"],
            ],
            headers=["Player", "Change", "Total"],
            tablefmt="github",
        )
        expected_embed.add_field(name="", value=f"```{expected_result_table}```")

        interaction.followup.send.assert_called_once()
        validate_embed(self, expected_embed, actual_embed)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_remove_ingots.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_add_remove_ingots_multiple_targets_ignore_duplicates(
        self, mock_storage, mock_validate_playername
    ):
        """Test that we ignore duplicate names and only award ingots once."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        target1 = create_test_member("atester", ROLES.MEMBER)
        reason = "testing"

        interaction = create_mock_discord_interaction(user=caller, members=[target1])

        mock_storage.read_members.return_value = [
            Member(id=target1.id, runescape_name=target1.display_name, ingots=5000),
        ]

        mock_validate_playername.side_effect = lambda _, name: (
            None,
            name,
        )

        await cmd_add_remove_ingots(
            interaction,
            f"{target1.display_name}, {target1.display_name} , {target1.display_name}",
            5000,
            reason,
        )

        mock_storage.update_members.assert_called_once_with(
            [
                Member(
                    id=target1.id, runescape_name=target1.display_name, ingots=10000
                ),
            ],
            caller.display_name,
            note=reason,
        )

        actual_embed = interaction.followup.send.call_args.kwargs["embed"]

        expected_embed = discord.Embed(
            title=" Add Ingots Result",
            description=(f"**Total Change:** +5,000\n" f"**Reason:** _{reason}_"),
        )
        expected_result_table = tabulate(
            [
                [target1.display_name, "+5,000", "10,000"],
            ],
            headers=["Player", "Change", "Total"],
            tablefmt="github",
        )
        expected_embed.add_field(name="", value=f"```{expected_result_table}```")

        interaction.followup.send.assert_called_once()
        validate_embed(self, expected_embed, actual_embed)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_remove_ingots.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_add_remove_ingots_ignore_unknown(
        self, mock_storage, mock_validate_playername
    ):
        """Test that we ignore unknown users but report them in output."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        target1 = create_test_member("atester", ROLES.MEMBER)
        target2 = create_test_member("btester", ROLES.MEMBER)
        reason = "testing"

        interaction = create_mock_discord_interaction(
            user=caller, members=[target1, target2]
        )

        mock_storage.read_members.return_value = [
            Member(id=target1.id, runescape_name=target1.display_name, ingots=5000),
            Member(id=target2.id, runescape_name=target2.display_name, ingots=10000),
        ]

        def patched_validate_playername(interaction, playername):
            if playername == target1.display_name:
                return target1, target1.display_name
            if playername == target2.display_name:
                return target1, target2.display_name
            raise ValueError()

        mock_validate_playername.side_effect = patched_validate_playername

        await cmd_add_remove_ingots(
            interaction,
            f"{target1.display_name},foo,{target2.display_name}",
            5000,
            reason,
        )

        mock_storage.update_members.assert_called_once_with(
            [
                Member(
                    id=target1.id, runescape_name=target1.display_name, ingots=10000
                ),
                Member(
                    id=target2.id, runescape_name=target2.display_name, ingots=15000
                ),
            ],
            caller.display_name,
            note=reason,
        )

        actual_embed = interaction.followup.send.call_args.kwargs["embed"]

        expected_embed = discord.Embed(
            title=" Add Ingots Result",
            description=(f"**Total Change:** +5,000\n" f"**Reason:** _{reason}_"),
        )
        expected_result_table = tabulate(
            [
                [target1.display_name, "+5,000", "10,000"],
                [target2.display_name, "+5,000", "15,000"],
                ["foo", "0", "unknown"],
            ],
            headers=["Player", "Change", "Total"],
            tablefmt="github",
        )
        expected_embed.add_field(name="", value=f"```{expected_result_table}```")

        interaction.followup.send.assert_called_once()
        validate_embed(self, expected_embed, actual_embed)

    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.send_error_response")
    @patch("ironforgedbot.commands.ingots.cmd_add_remove_ingots.validate_playername")
    @patch(
        "ironforgedbot.commands.ingots.cmd_add_remove_ingots.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_add_remove_ingots_report_insufficient_funds(
        self, mock_storage, mock_validate_playername, mock_send_error_response
    ):
        """Test that we report insufficient funds and don't process."""
        caller = create_test_member("leader", ROLES.LEADERSHIP)
        target1 = create_test_member("atester", ROLES.MEMBER)
        target2 = create_test_member("btester", ROLES.MEMBER)
        target3 = create_test_member("ctester", ROLES.MEMBER)
        reason = "testing"

        interaction = create_mock_discord_interaction(
            user=caller, members=[target1, target2, target3]
        )

        mock_storage.read_members.return_value = [
            Member(id=target1.id, runescape_name=target1.display_name, ingots=5000),
            Member(id=target2.id, runescape_name=target2.display_name, ingots=10000),
            Member(id=target3.id, runescape_name=target3.display_name, ingots=125000),
        ]

        mock_validate_playername.side_effect = lambda _, name: (
            None,
            name,
        )

        await cmd_add_remove_ingots(
            interaction,
            f"{target1.display_name},{target2.display_name},{target3.display_name}",
            -10000,
            reason,
        )

        mock_storage.update_members.assert_called_once_with(
            [
                Member(id=target2.id, runescape_name=target2.display_name, ingots=0),
                Member(
                    id=target3.id, runescape_name=target3.display_name, ingots=115000
                ),
            ],
            caller.display_name,
            note=reason,
        )

        expected_error_table = tabulate(
            [["Available:", "5,000"], ["Requested:", "-10,000"]], tablefmt="plain"
        )
        mock_send_error_response.assert_awaited_with(
            interaction,
            (
                f"Member **{target1.display_name}** does not have enough ingots.\n"
                f"No action taken.\n```{expected_error_table}```"
            ),
        )

        actual_result_embed = interaction.followup.send.call_args.kwargs["embed"]

        expected_results_embed = discord.Embed(
            title=" Remove Ingots Result",
            description=(f"**Total Change:** +5,000\n" f"**Reason:** _{reason}_"),
        )
        expected_result_table = tabulate(
            [
                [target1.display_name, "0", "5,000"],
                [target2.display_name, "-10,000", "0"],
                [target3.display_name, "-10,000", "115,000"],
            ],
            headers=["Player", "Change", "Total"],
            tablefmt="github",
        )
        expected_results_embed.add_field(
            name="", value=f"```{expected_result_table}```"
        )

        interaction.followup.send.assert_called_once()
        validate_embed(self, expected_results_embed, actual_result_embed)
