import asyncio
import random
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import discord

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

    @patch("main.validate_protected_request")
    async def test_syncmembers(self, mock_validate_protected_request):
        """Test that sheet can be updated to only members in Discord."""
        caller = helper_create_member("leader", ROLES.LEADERSHIP)

        mock_validate_protected_request.return_value = (
            caller,
            caller.display_name,
        )

        guild = Mock(discord.Guild)

        member1 = helper_create_member("member1", ROLES.MEMBER, "johnnycache")
        member2 = helper_create_member("member2", ROLES.MEMBER)
        member3 = helper_create_member("member3", ROLES.MEMBER)
        member5 = helper_create_member("member5", ROLES.MEMBER, "")
        guild.members = [member1, member2, member3, member5]

        self.mock_interaction.user = caller
        self.mock_interaction.guild = guild

        mock_storage = MagicMock()
        mock_storage.read_members.return_value = [
            Member(id=member1.id, runescape_name="member1", ingots=200),
            # In storage, but nick is not set.
            Member(id=member2.id, runescape_name="Crimson chin", ingots=400),
            Member(id=13, runescape_name="member4", ingots=1000),
        ]

        commands = main.IronForgedCommands(MagicMock(), MagicMock(), mock_storage, "")

        await commands.syncmembers(self.mock_interaction)

        mock_storage.add_members.assert_called_once_with(
            [Member(id=member3.id, runescape_name="member3", ingots=0)],
            "User Joined Server",
        )

        mock_storage.remove_members.assert_called_once_with(
            [Member(id=13, runescape_name="member4", ingots=1000)], "User Left Server"
        )

        mock_storage.update_members.assert_called_once_with(
            [
                Member(id=member1.id, runescape_name="johnnycache", ingots=200),
                Member(id=member2.id, runescape_name="member2", ingots=400),
            ],
            "Name Change",
        )
