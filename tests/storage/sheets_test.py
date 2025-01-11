import json
import os
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytz
from googleapiclient.discovery import build
from googleapiclient.http import HttpMock, HttpMockSequence
from ironforgedbot.storage.sheets import SheetsStorage
from ironforgedbot.storage.types import Member, StorageError

TIMEZONE = "America/Los_Angeles"


class TestSheetsStorage(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["TZ"] = "UTC"
        import time

        time.tzset()

    async def test_read_member(self):
        sheets_read_response = {"values": [["johnnycache", "2000", "123456"]]}

        http = HttpMock(headers={"status": "200"})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")

        client = SheetsStorage(sheets_client, "")

        expected = Member(id=123456, runescape_name="johnnycache", ingots=2000)

        self.assertEqual(await client.read_member("johnnycache"), expected)

    async def test_read_member_not_found(self):
        sheets_read_response = {"values": [["johnnycache", "2000", "123456"]]}

        http = HttpMock(headers={"status": "200"})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")

        client = SheetsStorage(sheets_client, "")

        self.assertEqual(await client.read_member("kennylogs"), None)

    async def test_read_member_handle_big_numbers(self):
        sheets_read_response = {
            "values": [["testrunbtw", "1000000000014870", "123456"]]
        }

        http = HttpMock(headers={"status": "200"})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")

        client = SheetsStorage(sheets_client, "")

        expected = Member(
            id=123456, runescape_name="testrunbtw", ingots=1000000000014870
        )

        self.assertEqual(await client.read_member("testrunbtw"), expected)

    async def test_read_member_handle_invalid_ingot_value(self):
        sheets_read_response = {"values": [["testrunbtw", "no-ingots", "123456"]]}

        http = HttpMock(headers={"status": "200"})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")

        client = SheetsStorage(sheets_client, "")

        with self.assertRaises(StorageError):
            await client.read_member("testrunbtw")

    async def test_read_members(self):
        sheets_read_response = {
            "values": [
                ["johnnycache", "2000", "123456"],
                ["kennylogs", "4000", "654321"],
            ]
        }

        http = HttpMock(headers={"status": "200"})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")

        client = SheetsStorage(sheets_client, "")

        expected = [
            Member(id=123456, runescape_name="johnnycache", ingots=2000),
            Member(id=654321, runescape_name="kennylogs", ingots=4000),
        ]

        self.assertEqual(await client.read_members(), expected)

    @patch("ironforgedbot.storage.sheets.datetime")
    async def test_add_members(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2023, 8, 26, 22, 33, 20)

        sheets_read_response = {"values": [["johnnycache", "2000", "123456"]]}

        http = HttpMockSequence(
            [
                ({"status": "200"}, json.dumps(sheets_read_response)),
                ({"status": "200"}, json.dumps("")),
                ({"status": "200"}, json.dumps("")),
            ]
        )

        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")
        client = SheetsStorage(sheets_client, "")

        await client.add_members(
            [Member(id=654321, runescape_name="kennylogs")], "User Joined Server"
        )

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps(
                {
                    "values": [
                        ["johnnycache", 2000, "123456"],
                        ["kennylogs", 0, "654321"],
                    ]
                }
            ),
        )

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps(
                {
                    "values": [
                        [
                            "kennylogs",
                            "2023-08-26 18:33:20 EDT-0400",
                            0,
                            0,
                            "User Joined Server",
                            "",
                        ]
                    ]
                }
            ),
        )

    @patch("ironforgedbot.storage.sheets.datetime")
    async def test_update_members(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2023, 8, 26, 22, 33, 20)
        johnnycache = Member(id=123456, runescape_name="johnnycache", ingots=2000)
        kennylogs = Member(id=123456, runescape_name="kennylogs", ingots=2000)
        sheets_read_response = {"values": [["johnnycache", "2000", "123456"]]}

        http = HttpMockSequence(
            [
                ({"status": "200"}, json.dumps(sheets_read_response)),
                ({"status": "200"}, json.dumps("")),
                ({"status": "200"}, json.dumps("")),
            ]
        )

        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")
        client = SheetsStorage(sheets_client, "")

        await client.update_members(
            [Member(id=123456, runescape_name="kennylogs", ingots=2000)], "leader"
        )

        self.assertEqual(
            http.request_sequence[1][2],
            json.dumps({"values": [["kennylogs", "2000", "123456"]]}),
        )

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps(
                {
                    "values": [
                        [
                            "johnnycache",
                            "2023-08-26 18:33:20 EDT-0400",
                            str(johnnycache),
                            str(kennylogs),
                            "leader",
                            "",
                        ]
                    ]
                }
            ),
        )

    @patch("ironforgedbot.storage.sheets.datetime")
    async def test_remove_members(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2023, 8, 26, 22, 33, 20)
        johnnycache = Member(id=123456, runescape_name="johnnycache", ingots=2000)
        sheets_read_response = {"values": [["johnnycache", "2000", "123456"]]}

        http = HttpMockSequence(
            [
                ({"status": "200"}, json.dumps(sheets_read_response)),
                ({"status": "200"}, json.dumps("")),
                ({"status": "200"}, json.dumps("")),
            ]
        )

        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")
        client = SheetsStorage(sheets_client, "")

        await client.remove_members([johnnycache], "User Left Server")

        self.assertEqual(
            http.request_sequence[1][2], json.dumps({"values": [["", "", ""]]})
        )

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps(
                {
                    "values": [
                        [
                            "johnnycache",
                            "2023-08-26 18:33:20 EDT-0400",
                            str(johnnycache),
                            0,
                            "User Left Server",
                            "",
                        ]
                    ]
                }
            ),
        )

    @patch("ironforgedbot.storage.sheets.datetime")
    async def test_start_raffle(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2023, 8, 26, 22, 33, 20)
        sheets_read_response = {"values": [["False"]]}

        http = HttpMockSequence(
            [
                ({"status": "200"}, json.dumps(sheets_read_response)),
                ({"status": "200"}, json.dumps("")),
                ({"status": "200"}, json.dumps("")),
            ]
        )

        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")
        client = SheetsStorage(sheets_client, "")

        await client.start_raffle("johnnycache")

        self.assertEqual(
            http.request_sequence[1][2], json.dumps({"values": [["True"]]})
        )

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps(
                {
                    "values": [
                        [
                            "",
                            "2023-08-26 18:33:20 EDT-0400",
                            "False",
                            "True",
                            "johnnycache",
                            "Started Raffle",
                        ]
                    ]
                }
            ),
        )

    async def test_start_raffle_already_ongoing(self):
        sheets_read_response = {"values": [["True"]]}

        http = HttpMock(headers={"status": "200"})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")

        client = SheetsStorage(sheets_client, "")

        with self.assertRaises(StorageError):
            await client.start_raffle("johnnycache")

    @patch("ironforgedbot.storage.sheets.datetime")
    async def test_end_raffle(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2023, 8, 26, 22, 33, 20)
        sheets_read_response = {"values": [["True"]]}

        http = HttpMockSequence(
            [
                ({"status": "200"}, json.dumps(sheets_read_response)),
                ({"status": "200"}, json.dumps("")),
                ({"status": "200"}, json.dumps("")),
            ]
        )

        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")
        client = SheetsStorage(sheets_client, "")

        await client.end_raffle("johnnycache")

        self.assertEqual(
            http.request_sequence[1][2], json.dumps({"values": [["False"]]})
        )

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps(
                {
                    "values": [
                        [
                            "",
                            "2023-08-26 18:33:20 EDT-0400",
                            "True",
                            "False",
                            "johnnycache",
                            "Ended Raffle",
                        ]
                    ]
                }
            ),
        )

    async def test_end_raffle_none_ongoing(self):
        sheets_read_response = {"values": [["False"]]}

        http = HttpMock(headers={"status": "200"})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")

        client = SheetsStorage(sheets_client, "")

        with self.assertRaises(StorageError):
            await client.end_raffle("johnnycache")

    async def test_read_raffle_tickets(self):
        sheets_read_response = {"values": [["12345", "20"]]}

        http = HttpMock(headers={"status": "200"})
        http.data = json.dumps(sheets_read_response)
        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")

        client = SheetsStorage(sheets_client, "")

        self.assertEqual({12345: 20}, await client.read_raffle_tickets())

    @patch("ironforgedbot.storage.sheets.datetime")
    async def test_add_raffle_tickets(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2023, 8, 26, 22, 33, 20)
        sheets_read_response = {"values": [["12345", "20"]]}

        http = HttpMockSequence(
            [
                ({"status": "200"}, json.dumps(sheets_read_response)),
                ({"status": "200"}, json.dumps("")),
                ({"status": "200"}, json.dumps("")),
            ]
        )

        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")
        client = SheetsStorage(sheets_client, "")

        await client.add_raffle_tickets(12345, 5)

        self.assertEqual(
            http.request_sequence[1][2], json.dumps({"values": [["12345", 25]]})
        )

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps(
                {
                    "values": [
                        [
                            12345,
                            "2023-08-26 18:33:20 EDT-0400",
                            20,
                            25,
                            12345,
                            "Assign 5 raffle tickets",
                        ]
                    ]
                }
            ),
        )

    @patch("ironforgedbot.storage.sheets.datetime")
    async def test_add_raffle_tickets_first_buy(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2023, 8, 26, 22, 33, 20)
        sheets_read_response = {"values": [[]]}

        http = HttpMockSequence(
            [
                ({"status": "200"}, json.dumps(sheets_read_response)),
                ({"status": "200"}, json.dumps("")),
                ({"status": "200"}, json.dumps("")),
            ]
        )

        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")
        client = SheetsStorage(sheets_client, "")

        await client.add_raffle_tickets(12345, 5)

        self.assertEqual(
            http.request_sequence[1][2], json.dumps({"values": [["12345", 5]]})
        )

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps(
                {
                    "values": [
                        [
                            12345,
                            "2023-08-26 18:33:20 EDT-0400",
                            0,
                            5,
                            12345,
                            "Assign 5 raffle tickets",
                        ]
                    ]
                }
            ),
        )

    @patch("ironforgedbot.storage.sheets.datetime")
    async def test_delete_raffle_tickets(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2023, 8, 26, 22, 33, 20)
        sheets_read_response = {"values": [["12345", "20"]]}

        http = HttpMockSequence(
            [
                ({"status": "200"}, json.dumps(sheets_read_response)),
                ({"status": "200"}, json.dumps("")),
                ({"status": "200"}, json.dumps("")),
            ]
        )

        sheets_client = build("sheets", "v4", http=http, developerKey="bloop")

        mock_datetime = MagicMock()
        mock_datetime.now.return_value = datetime.fromtimestamp(
            1693100000, tz=pytz.timezone(TIMEZONE)
        )

        client = SheetsStorage(sheets_client, "")

        await client.delete_raffle_tickets("johnnycache")

        self.assertEqual(
            http.request_sequence[1][2], json.dumps({"values": [["", ""]]})
        )

        self.assertEqual(
            http.request_sequence[2][2],
            json.dumps(
                {
                    "values": [
                        [
                            "",
                            "2023-08-26 18:33:20 EDT-0400",
                            "",
                            "",
                            "johnnycache",
                            "Cleared all raffle tickets",
                        ]
                    ]
                }
            ),
        )
