from datetime import datetime
import json
import unittest
from unittest.mock import MagicMock
from googleapiclient.discovery import build
from googleapiclient.http import HttpMock, HttpMockSequence

from ironforgedbot.storage.types import Member, StorageError
from ironforgedbot.storage.sheets import SheetsStorage


class TestSheetsStorage(unittest.TestCase):

    def test_read_member(self):
        sheets_read_response = {'values': [
            ['johnnycache', '2000', '123456']]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        client = SheetsStorage(sheets_client, '')

        expected = Member(
            id=123456, runescape_name='johnnycache', ingots=2000)

        self.assertEqual(client.read_member('johnnycache'), expected)

    def test_read_member_not_found(self):
        sheets_read_response = {'values': [
            ['johnnycache', '2000', '123456']]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        client = SheetsStorage(sheets_client, '')

        self.assertEqual(client.read_member('kennylogs'), None)

    def test_read_members(self):
        sheets_read_response = {'values': [
            ['johnnycache', '2000', '123456'],
            ['kennylogs', '4000', '654321']]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        client = SheetsStorage(sheets_client, '')

        expected = [
            Member(id=123456, runescape_name='johnnycache', ingots=2000),
            Member(id=654321, runescape_name='kennylogs', ingots=4000)]

        self.assertEqual(client.read_members(), expected)

    def test_add_members(self):
        sheets_read_response = {'values': [
            ['johnnycache', '2000', '123456']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        # Sat Aug 26 06:33:20 PM PDT 2023
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        client = SheetsStorage(sheets_client, '', clock=mock_datetime)

        client.add_members(
            [Member(id=654321, runescape_name='kennylogs')],
            'User Joined Server')

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [
                ['johnnycache', 2000, '123456'],
                ['kennylogs', 0, '654321']]}))

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps({'values': [
                ['kennylogs', '08/26/2023, 18:33:20', 0, 0, 'User Joined Server', '']]}))

    def test_update_members(self):
        johnnycache = Member(id=123456, runescape_name='johnnycache', ingots=2000)
        kennylogs = Member(id=123456, runescape_name='kennylogs', ingots=2000)
        sheets_read_response = {'values': [
            ['johnnycache', '2000', '123456']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        # Sat Aug 26 06:33:20 PM PDT 2023
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        client = SheetsStorage(sheets_client, '', clock=mock_datetime)

        client.update_members(
            [Member(id=123456, runescape_name='kennylogs', ingots=2000)],
            'leader')

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [
                ['kennylogs', 2000, '123456']]}))

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps({'values': [
                ['johnnycache', '08/26/2023, 18:33:20', str(johnnycache), str(kennylogs), 'leader', '']]}))

    def test_remove_members(self):
        johnnycache = Member(id=123456, runescape_name='johnnycache', ingots=2000)
        sheets_read_response = {'values': [
            ['johnnycache', '2000', '123456']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        # Sat Aug 26 06:33:20 PM PDT 2023
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        client = SheetsStorage(sheets_client, '', clock=mock_datetime)

        client.remove_members([johnnycache], 'User Left Server')

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [['', '', '']]}))

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps({'values': [
                ['johnnycache', '08/26/2023, 18:33:20', str(johnnycache), 0, 'User Left Server', '']]}))

    def test_start_raffle(self):
        sheets_read_response = {'values': [['False']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build('sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        client = SheetsStorage(sheets_client, '', clock=mock_datetime)

        client.start_raffle('johnnycache')

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [['True']]}))

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps({'values': [
                ['', '08/26/2023, 18:33:20', 'False', 'True', 'johnnycache', 'Started Raffle']]}))

    def test_start_raffle_already_ongoing(self):
        sheets_read_response = {'values': [['True']]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        client = SheetsStorage(sheets_client, '')

        with self.assertRaises(StorageError):
            client.start_raffle('johnnycache')

    def test_end_raffle(self):
        sheets_read_response = {'values': [['True']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build('sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        client = SheetsStorage(sheets_client, '', clock=mock_datetime)

        client.end_raffle('johnnycache')

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [['False']]}))

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps({'values': [
                ['', '08/26/2023, 18:33:20', 'True', 'False', 'johnnycache', 'Ended Raffle']]}))

    def test_end_raffle_none_ongoing(self):
        sheets_read_response = {'values': [['False']]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        client = SheetsStorage(sheets_client, '')

        with self.assertRaises(StorageError):
            client.end_raffle('johnnycache')

    def test_read_raffle_tickets(self):
        sheets_read_response = {'values': [['12345', '20']]}

        http = HttpMock(headers={'status': '200'})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build(
            'sheets', 'v4', http=http, developerKey='bloop')

        client = SheetsStorage(sheets_client, '')

        self.assertEqual(
            {12345: 20}, client.read_raffle_tickets())

    def test_add_raffle_tickets(self):
        sheets_read_response = {'values': [['12345', '20']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build('sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        client = SheetsStorage(sheets_client, '', clock=mock_datetime)

        client.add_raffle_tickets(12345, 5)

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [[12345, 25]]}))

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps({'values': [
                [12345, '08/26/2023, 18:33:20', 20, 25, 12345, 'Bought raffle tickets']]}))

    def test_add_raffle_tickets_first_buy(self):
        sheets_read_response = {'values': [[]]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build('sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        client = SheetsStorage(sheets_client, '', clock=mock_datetime)

        client.add_raffle_tickets(12345, 5)

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [[12345, 5]]}))

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps({'values': [
                [12345, '08/26/2023, 18:33:20', 0, 5, 12345, 'Bought raffle tickets']]}))

    def test_delete_raffle_tickets(self):
        sheets_read_response = {'values': [['12345', '20']]}

        http = HttpMockSequence([
            ({'status': '200'}, json.dumps(sheets_read_response)),
            ({'status': '200'}, json.dumps('')),
            ({'status': '200'}, json.dumps(''))])

        sheets_client = build('sheets', 'v4', http=http, developerKey='bloop')

        mock_datetime = MagicMock()
        mock_datetime.now.return_value = datetime.fromtimestamp(1693100000)

        client = SheetsStorage(sheets_client, '', clock=mock_datetime)

        client.delete_raffle_tickets('johnnycache')

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({'values': [['', '']]}))

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps({'values': [
                ['', '08/26/2023, 18:33:20', '', '', 'johnnycache', 'Cleared all raffle tickets']]}))
