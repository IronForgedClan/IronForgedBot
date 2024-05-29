import asyncio
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import discord
from parameterized import parameterized

import main
from ironforgedbot.storage.types import Member
from ironforgedbot.common.helpers import (
    validate_playername,
)
from ironforgedbot.common.roles import ROLES


def helper_create_member(name: str, role: ROLES) -> discord.User:
    discord_role = Mock(spec=discord.Role)
    discord_role.name = role

    user = Mock(spec=discord.User)
    user.roles = [role]
    user.name = name
    user.nick = name
    user.display_name = name

    return user


class TestIronForgedBot(unittest.IsolatedAsyncioTestCase):
    # logging.disable(logging.CRITICAL)

    @classmethod
    def setUpClass(cls):
        cls.loop = asyncio.new_event_loop()
        cls.patch_find_emoji = patch("main.find_emoji", return_value="")
        cls.patch_find_emoji.start()

    @classmethod
    def tearDownClass(cls):
        cls.loop.close()
        cls.patch_find_emoji.stop()

    def setUp(self):
        self.mock_interaction = AsyncMock(spec=discord.Interaction)
        self.mock_interaction.followup = AsyncMock()
        self.mock_interaction.is_expired = Mock()
        self.mock_interaction.is_expired.return_value = False
        self.mock_interaction.response = AsyncMock()
        self.mock_interaction.guild = Mock()
        self.mock_interaction.guild.members = []

    @parameterized.expand(
        [
            ({"SHEETID": "blorp", "GUILDID": "bleep", "BOT_TOKEN": "bloop"}, True),
            ({"SHEETID": "blorp"}, False),
            ({"GUILDID": "bleep"}, False),
            ({"BOT_TOKEN": "bloop"}, False),
        ]
    )
    def test_validate_initial_config(self, config, expected):
        """Test that all required fields are present in config."""
        self.assertEqual(main.validate_initial_config(config), expected)

    @parameterized.expand(
        [
            ("johnnycache", None, "johnnycache"),
            ("123456789012", None, "123456789012"),
            ("a", None, "a"),
            (
                "longinvalidname",
                ValueError,
                "RSN can only be 1-12 characters long",
            ),
        ]
    )
    @patch("main.validate_user_request")
    async def test_ingots(self, mock_validate_user_request):
        """Test that ingots for given player are returned to user."""
        player = "johnnycache"
        player_id = 123456

        mock_validate_user_request.return_value = (
            helper_create_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage = Mock()
        mock_storage.read_member.return_value = Member(
            id=player_id, runescape_name=player, ingots=2000
        )

        commands = main.IronForgedCommands(Mock(), Mock(), mock_storage, "")
        await commands.ingots(self.mock_interaction, "johnnycache")

        self.mock_interaction.followup.send.assert_called_once_with(
            "johnnycache has 2,000 ingots "
        )

    @patch("main.send_error_response")
    @patch("main.validate_user_request")
    async def test_ingots_user_not_in_spreadsheet(
        self, mock_validate_user_request, mock_send_error_response
    ):
        """Test that a missing player shows 0 ingots."""
        player = "johnnycache"

        mock_validate_user_request.return_value = (
            helper_create_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage = MagicMock()
        mock_storage.read_member.return_value = None

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        await commands.ingots(self.mock_interaction, player)

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction, f"Member '{player}' not found in spreadsheet"
        )

    @patch("main.validate_protected_request")
    async def test_addingots(self, mock_validate_protected_request):
        """Test that ingots can be added to a user."""
        leader_name = "leader"
        playername = "johnnycache"
        player_id = 123456

        mock_validate_protected_request.return_value = (
            helper_create_member(leader_name, ROLES.LEADERSHIP),
            playername,
        )

        mock_storage = MagicMock()
        mock_storage.read_member.return_value = Member(
            id=player_id, runescape_name=playername, ingots=5000
        )

        bot = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")

        await bot.addingots(self.mock_interaction, playername, 5000)

        mock_storage.update_members.assert_called_once_with(
            [Member(id=player_id, runescape_name=playername, ingots=10000)],
            leader_name,
            note="None",
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            f"Added 5,000 ingots to {playername}; reason: None. They now have 10,000 ingots "
        )

    @patch("main.send_error_response")
    @patch("main.validate_protected_request")
    async def test_addingots_player_not_found(
        self, mock_validate_protected_request, mock_send_error_response
    ):
        """Test that a missing player is surfaced to caller."""
        leader_name = "leader"
        playername = "johnnycache"

        mock_validate_protected_request.return_value = (
            helper_create_member(leader_name, ROLES.LEADERSHIP),
            playername,
        )

        mock_storage = MagicMock()
        mock_storage.read_member.return_value = None

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        await commands.addingots(self.mock_interaction, playername, 5)

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction, f"Member '{playername}' not found in spreadsheet"
        )

    @patch("main.send_error_response")
    async def test_addingots_permission_denied(
        self,
        mock_send_error_response,
    ):
        """Test that non-leadership role can't add ingots."""
        guild = AsyncMock(discord.Guild)
        caller = helper_create_member("1eader", ROLES.MEMBER)
        member = helper_create_member("member", ROLES.MEMBER)
        guild.members = [caller, member]
        self.mock_interaction.user = caller
        self.mock_interaction.guild = guild

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")

        await commands.addingots(self.mock_interaction, member.name, 5)

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction,
            f"Member '{caller.display_name}' does not have permission for this action",
        )

    @patch("main.validate_protected_request")
    def test_addingots_bulk(self, mock_validate_protected_request):
        """Test that ingots can be added to multiple users."""
        leader_name = "leader"
        player1 = "johnnycache"
        player1_id = 123456
        player2 = "kennylogs"
        player2_id = 654321

        mock_validate_protected_request.return_value = (
            helper_create_member(leader_name, ROLES.LEADERSHIP),
            leader_name,
        )

        mock_storage = MagicMock()
        mock_storage.read_members.return_value = [
            Member(id=player1_id, runescape_name=player1, ingots=5000),
            Member(id=player2_id, runescape_name=player2, ingots=400),
        ]

        mo = mock_open()

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")

        with patch("builtins.open", mo):
            self.loop.run_until_complete(
                commands.addingotsbulk(
                    self.mock_interaction, f"{player1},{player2}", 5000
                )
            )

        mock_storage.update_members.assert_called_once_with(
            [
                Member(id=player1_id, runescape_name=player1, ingots=10000),
                Member(id=player2_id, runescape_name=player2, ingots=5400),
            ],
            leader_name,
            note="None",
        )

        mo().write.assert_called_once_with(
            f"Added 5,000 ingots to {player1}. They now have 10,000 ingots\nAdded 5,000 ingots to {player2}. They now have 5,400 ingots"
        )

    @patch("main.validate_protected_request")
    def test_addingots_bulk_whitespace_stripped(self, mock_validate_protected_request):
        """Test that ingots can be added to multiple users."""
        leader_name = "leader"

        mock_validate_protected_request.return_value = (
            helper_create_member(leader_name, ROLES.LEADERSHIP),
            leader_name,
        )

        mock_storage = MagicMock()
        mock_storage.read_members.return_value = [
            Member(id=123456, runescape_name="johnnycache", ingots=5000),
            Member(id=654321, runescape_name="kennylogs", ingots=400),
        ]

        mo = mock_open()

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        with patch("builtins.open", mo):
            # User adds whitespace between args.
            self.loop.run_until_complete(
                commands.addingotsbulk(
                    self.mock_interaction, "johnnycache, skagul tosti", 5000
                )
            )

        mock_storage.update_members.assert_called_once_with(
            [Member(id=123456, runescape_name="johnnycache", ingots=10000)],
            "leader",
            note="None",
        )

        mo().write.assert_called_once_with(
            """Added 5,000 ingots to johnnycache. They now have 10,000 ingots
skagul tosti not found in storage."""
        )

    @patch("main.send_error_response")
    @patch("main.validate_protected_request")
    def test_addingots_bulk_player_fail_validation(
        self, mock_validate_protected_request, mock_send_error_response
    ):
        """Test that a missing player is surfaced to caller."""
        leader_name = "leader"
        bad_name = "somesuperlongfakename"

        mock_validate_protected_request.return_value = (
            helper_create_member(leader_name, ROLES.LEADERSHIP),
            leader_name,
        )

        mock_storage = MagicMock()
        mock_storage.read_member.return_value = None

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(
            commands.addingotsbulk(self.mock_interaction, bad_name, 5)
        )

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction, "RSN can only be 1-12 characters long"
        )

    @patch("main.send_error_response")
    def test_addingots_bulk_permission_denied(self, mock_send_error_response):
        """Test that non-leadership role can't add ingots."""
        guild = AsyncMock(discord.Guild)
        caller = helper_create_member("1eader", ROLES.MEMBER)
        member = helper_create_member("member", ROLES.MEMBER)
        guild.members = [caller, member]

        self.mock_interaction.user = caller
        self.mock_interaction.guild = guild

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.addingotsbulk(self.mock_interaction, caller.name, 500)
        )

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction,
            f"Member '{caller.name}' does not have permission for this action",
        )

    def test_updateingots(self):
        """Test that ingots can be written for a player."""
        mock_storage = MagicMock()
        mock_storage.read_member.return_value = Member(
            id=123456, runescape_name="johnnycache", ingots=10000
        )

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(
            commands.updateingots(self.mock_interaction, "johnnycache", 4000)
        )

        mock_storage.update_members.assert_called_once_with(
            [Member(id=123456, runescape_name="johnnycache", ingots=4000)],
            "leader",
            note="None",
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            "Set ingot count to 4,000 for johnnycache. Reason: None "
        )

    def test_updateingots_player_not_found(self):
        """Test that a missing player is surfaced to caller."""
        mock_storage = MagicMock()
        mock_storage.read_member.return_value = None

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(
            commands.updateingots(self.mock_interaction, "kennylogs", 400)
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            "kennylogs wasn't found."
        )

    def test_updateingots_permission_denied(self):
        """Test that only leadership can update ingots."""
        member = MagicMock()
        member.name = "johnnycache"

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.updateingots(mock_interaction, "kennylogs", 5)
        )

        mock_interaction.response.send_message.assert_called_once_with(
            "PERMISSION_DENIED: johnnycache is not in a leadership role."
        )

    def test_raffleadmin_permission_denied(self):
        member = MagicMock()
        member.name = "johnnycache"

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.raffleadmin(mock_interaction, "start_raffle")
        )

        mock_interaction.followup.send.assert_called_once_with(
            "PERMISSION_DENIED: johnnycache is not in a leadership role."
        )

    def test_raffleadmin_start_raffle(self):
        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.raffleadmin(self.mock_interaction, "start_raffle")
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            "Started raffle! Members can now use ingots to purchase tickets."
        )

    def test_raffleadmin_end_raffle(self):
        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.raffleadmin(self.mock_interaction, "end_raffle")
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            "Raffle ended! Members can no longer purchase tickets."
        )

    def test_raffleadmin_choose_winner(self):
        member = Member(id=12345, runescape_name="johnnycache")

        mock_storage = MagicMock()
        mock_storage.read_raffle_tickets.return_value = {12345: 25}
        mock_storage.read_members.return_value = [member]

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(
            commands.raffleadmin(self.mock_interaction, "choose_winner")
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            "johnnycache has won 62500 ingots out of 25 entries!"
        )

    def test_raffletickets_no_nickname_set(self):
        member = MagicMock()
        member.name = "member1"
        member.nick = None

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(commands.raffletickets(mock_interaction))

        mock_interaction.followup.send.assert_called_once_with(
            "FAILED_PRECONDITION: member1 does not have a nickname set."
        )

    def test_raffletickets_user_not_found(self):
        mock_user = MagicMock()
        mock_user.nick = "johnnycache"

        mock_interaction = AsyncMock()
        mock_interaction.user = mock_user
        mock_interaction.response = AsyncMock()

        mock_storage = MagicMock()
        mock_storage.read_member.return_value = None
        mock_storage.read_raffle_tickets.return_value = {12345: 25}

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(commands.raffletickets(mock_interaction))

        mock_interaction.followup.send.assert_called_once_with(
            "johnnycache not found in storage, please reach out to leadership."
        )

    def test_raffletickets(self):
        mock_user = MagicMock()
        mock_user.nick = "johnnycache"

        mock_interaction = AsyncMock()
        mock_interaction.user = mock_user
        mock_interaction.response = AsyncMock()

        mock_storage = MagicMock()
        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name="johnnycache"
        )
        mock_storage.read_raffle_tickets.return_value = {12345: 25}

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(commands.raffletickets(mock_interaction))

        mock_interaction.followup.send.assert_called_once_with(
            "johnnycache has 25 tickets!"
        )

    def test_buyraffletickets_missing_nickname(self):
        mock_user = MagicMock()
        mock_user.name = "member1"
        mock_user.nick = None

        mock_interaction = AsyncMock()
        mock_interaction.user = mock_user
        mock_interaction.response = AsyncMock()

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(commands.buyraffletickets(mock_interaction, 1))

        mock_interaction.followup.send.assert_called_once_with(
            "FAILED_PRECONDITION: member1 does not have a nickname set."
        )

    def test_buyraffletickets_not_enough_ingots(self):
        mock_user = MagicMock()
        mock_user.name = "member1"
        mock_user.nick = "johnnycache"

        mock_interaction = AsyncMock()
        mock_interaction.user = mock_user
        mock_interaction.response = AsyncMock()

        mock_storage = MagicMock()
        mock_storage.read_raffle.return_value = True
        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name="johnnycache", ingots=5000
        )

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(commands.buyraffletickets(mock_interaction, 5))

        mock_interaction.followup.send.assert_called_once_with(
            """johnnycache does not have enough ingots for 5 tickets.
Cost: 25000, current ingots: 5000"""
        )

    def test_buyraffletickets(self):
        mock_user = MagicMock()
        mock_user.name = "member1"
        mock_user.nick = "johnnycache"

        mock_interaction = AsyncMock()
        mock_interaction.user = mock_user
        mock_interaction.response = AsyncMock()

        mock_storage = MagicMock()
        mock_storage.read_raffle.return_value = True
        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name="johnnycache", ingots=25000
        )

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(commands.buyraffletickets(mock_interaction, 1))

        mock_interaction.followup.send.assert_called_once_with(
            "johnnycache successfully bought 1 tickets for 5000 ingots!"
        )

    def test_syncmembers(self):
        """Test that sheet can be updated to only members in Discord."""
        mock_discord_client = MagicMock()
        mock_guild = MagicMock()
        mock_discord_client.get_guild.return_value = mock_guild

        member_role = MagicMock()
        member_role.name = "Member"

        member1 = MagicMock()
        member1.id = 1
        member1.name = "member1"
        member1.nick = "Johnnycache"
        member1.roles = [member_role]

        member2 = MagicMock()
        member2.id = 2
        member2.name = "member2"
        member2.nick = None
        member2.roles = [member_role]

        member3 = MagicMock()
        member3.id = 3
        member3.name = "member3"
        member3.nick = "member3"
        member3.roles = [member_role]

        # Not in members & no nick, ignored.
        member5 = MagicMock()
        member5.id = 5
        member5.name = "member5"
        member5.nick = None

        mock_guild.members = [member1, member2, member3]

        mock_storage = MagicMock()
        mock_storage.read_members.return_value = [
            Member(id=1, runescape_name="member1", ingots=200),
            # In storage, but nick is not set.
            Member(id=2, runescape_name="Crimson chin", ingots=400),
            Member(id=4, runescape_name="member4", ingots=1000),
        ]

        mo = mock_open()

        commands = main.IronForgedCommands(
            MagicMock(), mock_discord_client, mock_storage, ""
        )

        with patch("builtins.open", mo):
            self.loop.run_until_complete(commands.syncmembers(self.mock_interaction))

        mock_storage.add_members.assert_called_once_with(
            [Member(id=3, runescape_name="member3", ingots=0)], "User Joined Server"
        )

        mock_storage.remove_members.assert_called_once_with(
            [Member(id=4, runescape_name="member4", ingots=1000)], "User Left Server"
        )

        mock_storage.update_members.assert_called_once_with(
            [
                Member(id=1, runescape_name="johnnycache", ingots=200),
                Member(id=2, runescape_name="member2", ingots=400),
            ],
            "Name Change",
        )

        mo().write.assert_called_once_with("""added user member3 because they joined
removed user member4 because they left the server
updated RSN for johnnycache
updated RSN for member2
""")
