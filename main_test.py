import asyncio
import datetime
from googleapiclient.discovery import build
from googleapiclient.http import HttpMock, HttpMockSequence
import json
from parameterized import parameterized
import requests
import unittest
from unittest.mock import AsyncMock, create_autospec, MagicMock, Mock, mock_open, patch


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

    @parameterized.expand([
        ({'SHEETID': 'blorp', 'GUILDID': 'bleep', 'BOT_TOKEN': 'bloop'}, True),
        ({'GUILDID': 'bleep'}, False),
        ({'BOT_TOKEN': 'bloop'}, False),
    ])
    def test_validate_initial_config(self, config, expected):
        self.assertEqual(main.validate_initial_config(config), expected)

    def test_score(self):
        mock_interaction = AsyncMock()
        mock_interaction.response = AsyncMock()

        response = requests.Response()
        response._content = bytes(hiscores_raw_response(), 'utf-8')

        with patch.object(requests, 'get', return_value=response):
            self.loop.run_until_complete(main.score(mock_interaction, 'johnnycache'))

        mock_interaction.response.send_message.assert_called_once_with(
            """johnnycache has 1626
Points from skills: 1256
Points from minigames & bossing: 370""")

    def test_breakdown(self):
        mock_interaction = AsyncMock()
        mock_interaction.response = AsyncMock()

        response = requests.Response()
        response._content = bytes(hiscores_raw_response(), 'utf-8')

        mo = mock_open()
        with patch.object(requests, 'get', return_value=response):
            with patch('builtins.open', mo):
                self.loop.run_until_complete(
                    main.breakdown(mock_interaction, 'johnnycache', '/'))

        mock_interaction.response.send_message.assert_called_once()
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
Total Skill Points: 1256 (77.24% of total)

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

Total Points: 1626
""")

    def test_ingots(self):
        mock_interaction = AsyncMock()
        mock_interaction.response = AsyncMock()

        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        self.loop.run_until_complete(main.ingots(
            mock_interaction, 'johnnycache', sheets_client,
            'bloop'))

        mock_interaction.response.send_message.assert_called_once_with(
            'johnnycache has 200 ingots')

    def test_ingots_user_not_present(self):
        mock_interaction = AsyncMock()
        mock_interaction.response = AsyncMock()

        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        self.loop.run_until_complete(main.ingots(
            mock_interaction, 'kennylogs', sheets_client,
            'bloop'))

        mock_interaction.response.send_message.assert_called_once_with(
            'kennylogs has 0 ingots')

    def test_addingots(self):
        role_payload = {
            'id': 0,
            'name': "Leadership",
        }
        role = discord.Role(guild=MagicMock(), state=MagicMock(), data=role_payload)

        member = MagicMock()
        member.roles = [role]
        member.nick = 'actor'

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        changelog_response = {'values': [
            ['kennylogs', '', '0', '0', 'johnnycache', '']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(changelog_response)),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        self.loop.run_until_complete(main.addingots(
            mock_interaction, 'johnnycache', 5, sheets_client, ''))

        # Ideally we could read the written file to assert data present.
        # But this is sheets, not a database, so asserting the value in
        # the PUT request is close enough.
        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [[205]]}))

        self.assertEqual(len(json.loads(http.request_sequence[3][2]).get('values', [])), 2)

        mock_interaction.response.send_message.assert_called_once_with(
            'Added 5 ingots to johnnycache')

    def test_addingots_player_not_found(self):
        role_payload = {
            'id': 0,
            'name': "Leadership",
        }
        role = discord.Role(guild=MagicMock(), state=MagicMock(), data=role_payload)

        member = MagicMock()
        member.roles = [role]

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        self.loop.run_until_complete(main.addingots(
            mock_interaction, 'kennylogs', 5, sheets_client, ''))

        mock_interaction.response.send_message.assert_called_once_with(
            'kennylogs wasn\'t found.')

    def test_addingots_permission_denied(self):
        role_payload = {
            'id': 0,
            'name': 'blorp',
        }
        role = discord.Role(guild=Mock(), state=Mock(), data=role_payload)

        member = MagicMock()
        member.name = 'johnnycache'

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        self.loop.run_until_complete(main.addingots(
            mock_interaction, 'kennylogs', 5, Mock(), ''))

        mock_interaction.response.send_message.assert_called_once_with(
            'PERMISSION_DENIED: johnnycache is not in a leadership role.')

    def test_updateingots(self):
        role_payload = {
            'id': 0,
            'name': 'Leadership',
        }
        role = discord.Role(guild=MagicMock(), state=MagicMock(), data=role_payload)

        member = MagicMock()
        member.roles = [role]
        member.nick = 'actor'

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        changelog_response = {'values': [
            ['kennylogs', '', '0', '0', 'johnnycache', '']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(changelog_response)),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        self.loop.run_until_complete(main.updateingots(
            mock_interaction, 'johnnycache', 400, sheets_client, ''))

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [[400]]}))

        self.assertEqual(
            len(json.loads(http.request_sequence[3][2]).get('values', [])),
            2)

        mock_interaction.response.send_message.assert_called_once_with(
            'Set ingot count to 400 for johnnycache')

    def test_updateingots_player_not_found(self):
        role_payload = {
            'id': 0,
            'name': "Leadership",
        }
        role = discord.Role(guild=MagicMock(), state=MagicMock(), data=role_payload)

        member = MagicMock()
        member.roles = [role]

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        sheets_read_response = {'values': [
            ['johnnycache', 200]]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        self.loop.run_until_complete(main.updateingots(
            mock_interaction, 'kennylogs', 400, sheets_client, ''))

        mock_interaction.response.send_message.assert_called_once_with(
            'kennylogs wasn\'t found.')

    def test_updateingots_permission_denied(self):
        role_payload = {
            'id': 0,
            'name': 'blorp',
        }
        role = discord.Role(guild=Mock(), state=Mock(), data=role_payload)

        member = MagicMock()
        member.name = 'johnnycache'

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        self.loop.run_until_complete(main.updateingots(
            mock_interaction, 'kennylogs', 5, Mock(), ''))

        mock_interaction.response.send_message.assert_called_once_with(
            'PERMISSION_DENIED: johnnycache is not in a leadership role.')

    def test_syncmembers(self):
        role_payload = {
            'id': 0,
            'name': "Leadership",
        }
        role = discord.Role(guild=MagicMock(), state=MagicMock(), data=role_payload)

        member = MagicMock()
        member.roles = [role]

        mock_interaction = AsyncMock()
        mock_interaction.user = member
        mock_interaction.response = AsyncMock()

        mock_discord_client = AsyncMock()
        mock_guild = MagicMock()
        mock_discord_client.fetch_guild.return_value = mock_guild

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

        class AsyncMemberFetcher(object):
            def __init__(self):
                self.items = [member1, member2, member3]

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return self.items.pop()
                except IndexError:
                    pass

                raise StopAsyncIteration

        mock_guild.fetch_members.return_value = AsyncMemberFetcher()

        sheets_read_response = {'values': [
            ['member1', '200', '1'],
            ['member4', '1000', '4'],
        ]}

        changelog_response = {'values': [
            ['kennylogs', '', '0', '0', 'johnnycache', '']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(changelog_response)),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        self.loop.run_until_complete(main.syncmembers(
            mock_interaction, mock_discord_client, sheets_client, ''))

        expected_body = {'values': [
            ['member1', 200, '1'],
            ['member3', 0, '3'],
        ]}

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps(expected_body))

        self.assertEqual(
            len(json.loads(http.request_sequence[3][2]).get('values', [])), 3)

