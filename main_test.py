import asyncio
from datetime import datetime
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch
from googleapiclient.discovery import build
from googleapiclient.http import HttpMock, HttpMockSequence
from parameterized import parameterized
import requests


import discord
import main


def hiscores_raw_response():
    """Hiscores constant for testing. Raw response from API.

    Called as a function to prevent unexpected
    mutations between tests affecting output.

    Equates to scores:
        skills: 1256
        activities: 370
    """
    scores = """380984,1903,76082901
883995,80,2030525
859722,80,1986799
870607,89,5052943
884097,88,4798524
984424,84,3179955
705152,73,1084703
754738,88,4772057
610234,83,2906155
192328,93,7236865
581217,80,2123851
467733,82,2503585
78690,99,13512762
284508,86,3729682
346375,81,2206940
304656,83,2747066
534264,73,1026949
293683,80,2057879
315243,81,2341976
720916,77,1524934
568550,80,1993041
210710,81,2282874
433661,76,1375258
153450,86,3607578
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
39982,797
6252,387
23070,200
77119,170
408140,34
601179,1
181563,5
-1,-1
-1,-1
-1,-1
41171,274
-1,-1
-1,-1
-1,-1
47407,674
5524,111
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
199114,168
-1,-1
73890,25
-1,-1
-1,-1
-1,-1
-1,-1
350114,18
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
199187,6
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
60667,190
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
-1,-1
246238,405
-1,-1
-1,-1

"""
    return scores


class TestIronForgedBot(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.loop = asyncio.get_event_loop()

    @classmethod
    def tearDownClass(cls):
        cls.loop.close()

    def setUp(self):
        self.leader_payload = {
            'id': 0,
            'name': "Leadership",
        }
        self.leader_role = discord.Role(
            guild=MagicMock(), state=MagicMock(), data=self.leader_payload)

        self.leader = MagicMock()
        self.leader.roles = [self.leader_role]
        self.leader.nick = 'leader'

        self.mock_interaction = AsyncMock()
        self.mock_interaction.user = self.leader
        self.mock_interaction.response = AsyncMock()

    @parameterized.expand([
        ({'SHEETID': 'blorp', 'GUILDID': 'bleep', 'BOT_TOKEN': 'bloop'}, True),
        ({'GUILDID': 'bleep'}, False),
        ({'BOT_TOKEN': 'bloop'}, False),
    ])
    def test_validate_initial_config(self, config, expected):
        """Test that all required fields are present in config."""
        self.assertEqual(main.validate_initial_config(config), expected)

    @parameterized.expand([
        ('johnnycache', True),
        ('somesuperlonginvalidname', False),
    ])
    def test_validate_player_name(self, player, expected):
        self.assertEqual(main.validate_player_name(player), expected)

    def test_score(self):
        """Test that the expected score is given to the user."""
        response = requests.Response()
        response._content = bytes(hiscores_raw_response(), 'utf-8')
        response.status_code = 200

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), MagicMock(), '', '')

        with patch.object(requests, 'get', return_value=response):
            self.loop.run_until_complete(commands.score(
                self.mock_interaction, 'johnnycache'))

        self.mock_interaction.followup.send.assert_called_once_with(
            """johnnycache has 1,626
Points from skills: 1,256
Points from minigames & bossing: 370""")

    def test_breakdown(self):
        """Test that full score is given to user."""
        response = requests.Response()
        response._content = bytes(hiscores_raw_response(), 'utf-8')
        response.status_code = 200

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), MagicMock(), '', '/')
        mo = mock_open()
        with patch.object(requests, 'get', return_value=response):
            with patch('builtins.open', mo):
                self.loop.run_until_complete(
                    commands.breakdown(self.mock_interaction, 'johnnycache'))

        self.mock_interaction.followup.send.assert_called_once()
        mo().write.assert_called_once_with(
            """---Points from Skills---
Attack: 20
Defence: 19
Strength: 50
Hitpoints: 47
Ranged: 31
Prayer: 30
Magic: 47
Cooking: 29
Woodcutting: 144
Fletching: 21
Fishing: 50
Firemaking: 131
Crafting: 106
Smithing: 44
Mining: 91
Herblore: 41
Agility: 68
Thieving: 23
Slayer: 50
Farming: 39
Runecraft: 76
Hunter: 27
Construction: 72
Total Skill Points: 1,256 (77.24% of total)

---Points from Minigames & Bossing---
Clue Scrolls (beginner): 38
Clue Scrolls (easy): 40
Clue Scrolls (medium): 51
Clue Scrolls (hard): 17
Clue Scrolls (elite): 1
Clue Scrolls (master): 10
Rifts closed: 39
Barrows Chests: 44
Bryophyta: 37
Dagannoth Rex: 2
Hespori: 22
Obor: 2
Tempoross: 27
Wintertodt: 40
Total Minigame & Bossing Points: 370 (22.76% of total)

Total Points: 1,626
""")

    def test_ingots(self):
        """Test that ingots for given player are returned to user."""
        sheets_read_response = {'values': [
            ['johnnycache', 2000]]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), sheets_client, '', '')
        self.loop.run_until_complete(commands.ingots(
            self.mock_interaction, 'johnnycache'))

        self.mock_interaction.followup.send.assert_called_once_with(
            'johnnycache has 2,000 ingots')

    def test_ingots_user_not_present(self):
        """Test that a missing player shows 0 ingots."""
        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), sheets_client, '', '')
        self.loop.run_until_complete(commands.ingots(
            self.mock_interaction, 'kennylogs'))

        self.mock_interaction.followup.send.assert_called_once_with(
            'kennylogs has 0 ingots')

    def test_addingots(self):
        """Test that ingots can be added to a user."""
        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        changelog_response = {'values': [
            ['kennylogs', '08/25/2023, 10:00:00', '0', '0', 'johnnycache', '']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(changelog_response)),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        # Sat Aug 26 06:33:20 PM PDT 2023
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), sheets_client, '', '', mock_datetime)
        self.loop.run_until_complete(commands.addingots(
            self.mock_interaction, 'johnnycache', 5000))

        # Ideally we could read the written file to assert data present.
        # But this is sheets, not a database, so asserting the value in
        # the PUT request is close enough.
        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [[5200]]}))

        self.assertEqual(
            http.request_sequence[3][2],
            json.dumps({'values': [
                ['johnnycache', '08/26/2023, 18:33:20', 200, 5200, 'leader', ''],
                ['kennylogs', '08/25/2023, 10:00:00', '0', '0', 'johnnycache', '']
            ]}),
        )

        self.mock_interaction.followup.send.assert_called_once_with(
            'Added 5,000 ingots to johnnycache')

    def test_addingots_player_not_found(self):
        """Test that a missing player is surfaced to caller."""
        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), sheets_client, '', '')
        self.loop.run_until_complete(commands.addingots(
            self.mock_interaction, 'kennylogs', 5))

        self.mock_interaction.followup.send.assert_called_once_with(
            'kennylogs wasn\'t found.')

    def test_addingots_permission_denied(self):
        """Test that non-leadership role can't add ingots."""
        member = MagicMock()
        member.name = 'johnnycache'

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), MagicMock(), '', '')
        self.loop.run_until_complete(commands.addingots(
            mock_interaction, 'kennylogs', 5))

        mock_interaction.response.send_message.assert_called_once_with(
            'PERMISSION_DENIED: johnnycache is not in a leadership role.')

    def test_updateingots(self):
        """Test that ingots can be written for a player."""
        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        changelog_response = {'values': [
            ['kennylogs', '08/25/2023, 10:00:00', '0', '0', 'johnnycache', '']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(changelog_response)),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        # Sat Aug 26 06:33:20 PM PDT 2023
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), sheets_client, '', '', mock_datetime)
        self.loop.run_until_complete(commands.updateingots(
            self.mock_interaction, 'johnnycache', 4000))

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [[4000]]}))

        self.assertEqual(
            http.request_sequence[3][2],
            json.dumps({'values': [
                ['johnnycache', '08/26/2023, 18:33:20', 200, 4000, 'leader', ''],
                ['kennylogs', '08/25/2023, 10:00:00', '0', '0', 'johnnycache', ''],
            ]}),
        )

        self.mock_interaction.followup.send(
            'Set ingot count to 4,000 for johnnycache')

    def test_updateingots_player_not_found(self):
        """Test that a missing player is surfaced to caller."""
        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), sheets_client, '', '')
        self.loop.run_until_complete(commands.updateingots(
            self.mock_interaction, 'kennylogs', 400))

        self.mock_interaction.followup.send.assert_called_once_with(
            'kennylogs wasn\'t found.')

    def test_updateingots_permission_denied(self):
        """Test that only leadership can update ingots."""
        member = MagicMock()
        member.name = 'johnnycache'

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        commands = main.IronForgedCommands(
            MagicMock(), MagicMock(), MagicMock(), '', '')
        self.loop.run_until_complete(commands.updateingots(
            mock_interaction, 'kennylogs', 5))

        mock_interaction.response.send_message.assert_called_once_with(
            'PERMISSION_DENIED: johnnycache is not in a leadership role.')

    def test_syncmembers(self):
        """Test that sheet can be updated to only members in Discord."""
        mock_discord_client = MagicMock()
        mock_guild = MagicMock()
        mock_discord_client.get_guild.return_value = mock_guild

        member1 = MagicMock()
        member1.id = 1
        member1.name = "member1"
        member1.nick = "member1"

        member2 = MagicMock()
        member2.id = 2
        member2.name = "member2"
        member2.nick = None

        member3 = MagicMock()
        member3.id = 3
        member3.name = "member3"
        member3.nick = "member3"

        mock_guild.members = [member1, member2, member3]

        sheets_read_response = {'values': [
            ['member1', '200', '1'],
            ['member4', '1000', '4'],
        ]}

        changelog_response = {'values': [
            ['kennylogs', '08/25/2023, 10:00:00', '0', '0', 'johnnycache', '']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(changelog_response)),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        # Sat Aug 26 06:33:20 PM PDT 2023
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        commands = main.IronForgedCommands(
            MagicMock(), mock_discord_client, sheets_client, '', '', mock_datetime)
        self.loop.run_until_complete(commands.syncmembers(
            self.mock_interaction))

        expected_body = {'values': [
            ['member1', 200, '1'],
            ['member3', 0, '3'],
        ]}

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps(expected_body))

        self.maxDiff = None
        self.assertEqual(
            http.request_sequence[3][2],
            json.dumps({'values': [
                ['member3', '08/26/2023, 18:33:20', 0, 0, 'User Joined Server', ''],
                ['member4', '08/26/2023, 18:33:20', '1000', 0, 'User Left Server', ''],
                ['kennylogs', '08/25/2023, 10:00:00', '0', '0', 'johnnycache', ''],
            ]}),
        )

#        self.assertEqual(
#            len(json.loads(http.request_sequence[3][2]).get('values', [])), 3)
