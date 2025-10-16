import asyncio
import json
from typing import Counter
import unittest
import aiohttp
from unittest.mock import AsyncMock, patch

from unittest.mock import Mock

from ironforgedbot.commands.holiday.trick_or_treat_handler import (
    TrickOrTreat,
    TrickOrTreatHandler,
)
from ironforgedbot.common.roles import ROLE

# from ironforgedbot.storage.types import Member  # Disabled for rewrite
from tests.helpers import (
    create_mock_discord_interaction,
    create_test_member,
    get_url_status_code,
)

# Mock Member class for temporary compatibility
Member = Mock

BOT_CHANGELOG_ENTRY = "[BOT] Trick or Treat"


@unittest.skip("Skipping until trick or treat implementation rewrite")
class TestTrickOrTreatHandler(unittest.IsolatedAsyncioTestCase):
    async def test_init(self):
        with patch("ironforgedbot.decorators.decorators.singleton", lambda x: x):
            handler = await TrickOrTreatHandler()
            expected_weights = [1 / item.value for item in TrickOrTreat]

            self.assertEqual(handler.gif_history, [])
            self.assertEqual(handler.thumbnail_history, [])
            self.assertEqual(handler.positive_message_history, [])
            self.assertEqual(handler.negative_message_history, [])
            self.assertEqual(handler.weights, expected_weights)

    @patch(
        "ironforgedbot.commands.holiday.trick_or_treat_handler.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_adjust_ingots_add(self, mock_storage):
        with patch("ironforgedbot.decorators.decorators.singleton", lambda x: x):
            caller = create_test_member("bob", [ROLE.MEMBER])
            interaction = create_mock_discord_interaction(user=caller)

            mock_storage.read_member.return_value = Member(
                id=caller.id, runescape_name=caller.display_name, ingots=5000
            )

            handler = await TrickOrTreatHandler()

            await handler._adjust_ingots(interaction, 5, caller)

            mock_storage.update_members.assert_called_once_with(
                [Member(id=caller.id, runescape_name=caller.display_name, ingots=5005)],
                caller.display_name,
                note=BOT_CHANGELOG_ENTRY,
            )

    @patch(
        "ironforgedbot.commands.holiday.trick_or_treat_handler.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_adjust_ingots_remove(self, mock_storage):
        with patch("ironforgedbot.decorators.decorators.singleton", lambda x: x):
            caller = create_test_member("bob", [ROLE.MEMBER])
            interaction = create_mock_discord_interaction(user=caller)

            mock_storage.read_member.return_value = Member(
                id=caller.id, runescape_name=caller.display_name, ingots=5000
            )

            handler = await TrickOrTreatHandler()

            await handler._adjust_ingots(interaction, -5, caller)

            mock_storage.update_members.assert_called_once_with(
                [Member(id=caller.id, runescape_name=caller.display_name, ingots=4995)],
                caller.display_name,
                note=BOT_CHANGELOG_ENTRY,
            )

    @patch(
        "ironforgedbot.commands.holiday.trick_or_treat_handler.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_adjust_ingots_member_has_none(self, mock_storage):
        with patch("ironforgedbot.decorators.decorators.singleton", lambda x: x):
            caller = create_test_member("bob", [ROLE.MEMBER])
            interaction = create_mock_discord_interaction(user=caller)

            mock_storage.read_member.return_value = Member(
                id=caller.id, runescape_name=caller.display_name, ingots=0
            )

            handler = await TrickOrTreatHandler()

            result = await handler._adjust_ingots(interaction, -5, caller)

            self.assertEqual(result, (None, None))
            mock_storage.update_members.assert_not_called()

    @patch(
        "ironforgedbot.commands.holiday.trick_or_treat_handler.STORAGE",
        new_callable=AsyncMock,
    )
    async def test_adjust_ingots_member_has_less_than_wanted_to_remove(
        self, mock_storage
    ):
        with patch("ironforgedbot.decorators.decorators.singleton", lambda x: x):
            caller = create_test_member("bob", [ROLE.MEMBER])
            interaction = create_mock_discord_interaction(user=caller)

            mock_storage.read_member.return_value = Member(
                id=caller.id, runescape_name=caller.display_name, ingots=1
            )

            handler = await TrickOrTreatHandler()

            result = await handler._adjust_ingots(interaction, -5, caller)

            self.assertEqual(result, (-1, 0))
            mock_storage.update_members.assert_called_once_with(
                [Member(id=caller.id, runescape_name=caller.display_name, ingots=0)],
                caller.display_name,
                note=BOT_CHANGELOG_ENTRY,
            )

    async def test_unique_gifs(self):
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            GIFS = data["GIFS"]

        duplicates = [gif for gif, count in Counter(GIFS).items() if count > 1]
        assert not duplicates, f"Duplicate gifs: {duplicates}"

    @unittest.skip("Network heavy, run only when necessary")
    async def test_gifs_return_200(self):
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            GIFS = data["GIFS"]

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in GIFS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(GIFS, results):
                assert result == 200, f"{url} returned status code {result}"

    async def test_unique_thumbnails(self):
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            THUMBNAILS = data["THUMBNAILS"]

        duplicates = [gif for gif, count in Counter(THUMBNAILS).items() if count > 1]
        assert not duplicates, f"Duplicate thumbnails: {duplicates}"

    @unittest.skip("Network heavy, run only when necessary")
    async def test_thumbnails_return_200(self):
        with open("data/trick_or_treat.json") as f:
            data = json.load(f)
            THUMBNAILS = data["THUMBNAILS"]

        async with aiohttp.ClientSession() as session:
            tasks = [get_url_status_code(session, url) for url in THUMBNAILS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(THUMBNAILS, results):
                assert result == 200, f"{url} returned status code {result}"
