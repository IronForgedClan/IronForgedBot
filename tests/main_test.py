import asyncio
import random
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import discord
from parameterized import parameterized

import main
from ironforgedbot.common.roles import ROLES
from ironforgedbot.storage.types import Member


def helper_create_member(name: str, role: ROLES, nick=None) -> discord.User:
    if nick is None:
        nick = name

    discord_role = Mock(spec=discord.Role)
    discord_role.name = role

    user = Mock(spec=discord.User)
    user.id = random.randint(100, 999)
    user.roles = [role]
    user.name = name
    user.nick = nick
    user.display_name = nick

    return user


class TestIronForgedBot(unittest.IsolatedAsyncioTestCase):
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

    @patch("main.validate_user_request")
    async def test_ingots(self, mock_validate_user_request):
        """Test that ingots for given player are returned to user."""
        user = helper_create_member("johnnycache", ROLES.MEMBER)

        mock_validate_user_request.return_value = (
            user,
            user.display_name,
        )

        mock_storage = Mock()
        mock_storage.read_member.return_value = Member(
            id=user.id, runescape_name=user.display_name, ingots=2000
        )

        commands = main.IronForgedCommands(Mock(), Mock(), mock_storage, "")
        await commands.ingots(self.mock_interaction, user.display_name)

        self.mock_interaction.followup.send.assert_called_once_with(
            f"{user.display_name} has 2,000 ingots "
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

    @patch("main.validate_protected_request")
    def test_updateingots(self, mock_validate_protected_request):
        """Test that ingots can be written for a player."""
        leader_name = "leader"
        playername = "johnnycache"
        player_id = 123456

        mock_validate_protected_request.return_value = (
            helper_create_member(leader_name, ROLES.LEADERSHIP),
            playername,
        )

        mock_storage = MagicMock()
        mock_storage.read_member.return_value = Member(
            id=player_id, runescape_name=playername, ingots=10000
        )

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(
            commands.updateingots(self.mock_interaction, playername, 4000)
        )

        mock_storage.update_members.assert_called_once_with(
            [Member(id=player_id, runescape_name=playername, ingots=4000)],
            leader_name,
            note="None",
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            f"Set ingot count to 4,000 for {playername}. Reason: None "
        )

    @patch("main.validate_protected_request")
    def test_updateingots_player_not_found(self, mock_validate_protected_request):
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
        self.loop.run_until_complete(
            commands.updateingots(self.mock_interaction, playername, 400)
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            f"{playername} wasn't found."
        )

    @patch("main.send_error_response")
    def test_updateingots_permission_denied(self, mock_send_error_response):
        """Test that only leadership can update ingots."""
        guild = AsyncMock(discord.Guild)
        caller = helper_create_member("1eader", ROLES.MEMBER)
        member = helper_create_member("member", ROLES.MEMBER)
        guild.members = [caller, member]

        self.mock_interaction.user = caller
        self.mock_interaction.guild = guild

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.updateingots(self.mock_interaction, member.name, 5)
        )

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction,
            f"Member '{caller.name}' does not have permission for this action",
        )

    @patch("main.send_error_response")
    def test_raffleadmin_permission_denied(self, mock_send_error_response):
        guild = AsyncMock(discord.Guild)
        caller = helper_create_member("1eader", ROLES.MEMBER)
        member = helper_create_member("member", ROLES.MEMBER)
        guild.members = [caller, member]

        self.mock_interaction.user = caller
        self.mock_interaction.guild = guild

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.raffleadmin(self.mock_interaction, "start_raffle")
        )

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction,
            f"Member '{caller.name}' does not have permission for this action",
        )

    @patch("main.validate_protected_request")
    def test_raffleadmin_start_raffle(self, mock_validate_protected_request):
        leader_name = "leader"
        playername = "johnnycache"

        mock_validate_protected_request.return_value = (
            helper_create_member(leader_name, ROLES.LEADERSHIP),
            playername,
        )

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.raffleadmin(self.mock_interaction, "start_raffle")
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            "Started raffle! Members can now use ingots to purchase tickets."
        )

    @patch("main.validate_protected_request")
    def test_raffleadmin_end_raffle(self, mock_validate_protected_request):
        leader_name = "leader"
        playername = "johnnycache"

        mock_validate_protected_request.return_value = (
            helper_create_member(leader_name, ROLES.LEADERSHIP),
            playername,
        )

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.raffleadmin(self.mock_interaction, "end_raffle")
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            "Raffle ended! Members can no longer purchase tickets."
        )

    @patch("main.validate_protected_request")
    def test_raffleadmin_choose_winner(self, mock_validate_protected_request):
        leader_name = "leader"
        playername = "johnnycache"

        mock_validate_protected_request.return_value = (
            helper_create_member(leader_name, ROLES.LEADERSHIP),
            playername,
        )

        member = Member(id=12345, runescape_name=playername)

        mock_storage = MagicMock()
        mock_storage.read_raffle_tickets.return_value = {12345: 25}
        mock_storage.read_members.return_value = [member]

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(
            commands.raffleadmin(self.mock_interaction, "choose_winner")
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            f"{playername} has won 62500 ingots out of 25 entries!"
        )

    @patch("main.send_error_response")
    def test_raffletickets_no_nickname_set(self, mock_send_error_response):
        guild = AsyncMock(discord.Guild)
        caller = helper_create_member("", ROLES.MEMBER)
        guild.members = [caller]

        self.mock_interaction.user = caller
        self.mock_interaction.guild = guild

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(commands.raffletickets(self.mock_interaction))

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction, "RSN can only be 1-12 characters long"
        )

    @patch("main.send_error_response")
    @patch("main.validate_user_request")
    def test_raffletickets_user_not_found(
        self, mock_validate_user_request, mock_send_error_response
    ):
        player = "johnnycache"

        mock_validate_user_request.return_value = (
            helper_create_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage = MagicMock()
        mock_storage.read_member.return_value = None
        mock_storage.read_raffle_tickets.return_value = {12345: 25}

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(commands.raffletickets(self.mock_interaction))

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction,
            f"{player} not found in storage, please reach out to leadership.",
        )

    @patch("main.validate_user_request")
    def test_raffletickets(self, mock_validate_user_request):
        player = "johnnycache"

        mock_validate_user_request.return_value = (
            helper_create_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage = MagicMock()
        mock_storage.read_member.return_value = Member(id=12345, runescape_name=player)
        mock_storage.read_raffle_tickets.return_value = {12345: 25}

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(commands.raffletickets(self.mock_interaction))

        self.mock_interaction.followup.send.assert_called_once_with(
            "johnnycache has 25 tickets!"
        )

    @patch("main.send_error_response")
    def test_buyraffletickets_missing_nickname(self, mock_send_error_response):
        guild = AsyncMock(discord.Guild)
        caller = helper_create_member("", ROLES.MEMBER)
        guild.members = [caller]

        self.mock_interaction.user = caller
        self.mock_interaction.guild = guild

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), MagicMock(), "")
        self.loop.run_until_complete(
            commands.buyraffletickets(self.mock_interaction, 1)
        )

        mock_send_error_response.assert_awaited_with(
            self.mock_interaction, "RSN can only be 1-12 characters long"
        )

    @patch("main.validate_user_request")
    def test_buyraffletickets_not_enough_ingots(self, mock_validate_user_request):
        player = "johnnycache"

        mock_validate_user_request.return_value = (
            helper_create_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage = MagicMock()
        mock_storage.read_raffle.return_value = True
        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name=player, ingots=5000
        )

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(
            commands.buyraffletickets(self.mock_interaction, 5)
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            f"""{player} does not have enough ingots for 5 tickets.
Cost: 25000, current ingots: 5000"""
        )

    @patch("main.validate_user_request")
    def test_buyraffletickets(self, mock_validate_user_request):
        player = "johnnycache"

        mock_validate_user_request.return_value = (
            helper_create_member(player, ROLES.MEMBER),
            player,
        )

        mock_storage = MagicMock()
        mock_storage.read_raffle.return_value = True
        mock_storage.read_member.return_value = Member(
            id=12345, runescape_name=player, ingots=25000
        )

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")
        self.loop.run_until_complete(
            commands.buyraffletickets(self.mock_interaction, 1)
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            f"{player} successfully bought 1 tickets for 5000 ingots!"
        )
