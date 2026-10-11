import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import discord

from ironforgedbot.common.welcome import (
    WelcomeMessage,
    format_welcome_content,
    load_welcome_messages,
    send_welcome_messages,
)


class TestLoadWelcomeMessages(unittest.TestCase):
    def test_loads_text_local_image_and_url_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = Path(temp_dir) / "welcome.json"
            data_path.write_text(
                json.dumps(
                    {
                        "messages": [
                            {"content": "Welcome one"},
                            {"content": "Welcome two", "image": "img/welcome.png"},
                            {
                                "content": "Welcome three",
                                "image": "https://example.com/welcome.png",
                            },
                        ]
                    }
                )
            )

            messages = load_welcome_messages(str(data_path))

        self.assertEqual(
            messages,
            [
                WelcomeMessage(content="Welcome one", image=None),
                WelcomeMessage(content="Welcome two", image="img/welcome.png"),
                WelcomeMessage(
                    content="Welcome three", image="https://example.com/welcome.png"
                ),
            ],
        )

    def test_rejects_empty_messages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = Path(temp_dir) / "welcome.json"
            data_path.write_text('{"messages": []}')

            with self.assertRaisesRegex(ValueError, "at least one"):
                load_welcome_messages(str(data_path))

    def test_rejects_invalid_image_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_path = Path(temp_dir) / "welcome.json"
            data_path.write_text(
                json.dumps(
                    {
                        "messages": [
                            {"content": "Welcome", "image": "ftp://host/image.png"}
                        ]
                    }
                )
            )

            with self.assertRaisesRegex(ValueError, "image"):
                load_welcome_messages(str(data_path))


class TestFormatWelcomeContent(unittest.TestCase):
    def test_replaces_channel_placeholders_with_discord_mentions(self):
        result = format_welcome_content(
            "Read {{RULES_CHANNEL}} and ask in {{BOT_COMMANDS_CHANNEL}}.",
            {
                "RULES_CHANNEL_ID": 123,
                "BOT_COMMANDS_CHANNEL_ID": 456,
            },
        )

        self.assertEqual(result, "Read <#123> and ask in <#456>.")

    def test_raises_when_placeholder_channel_is_not_configured(self):
        with self.assertRaisesRegex(ValueError, "RULES_CHANNEL_ID"):
            format_welcome_content("Read {{RULES_CHANNEL}}.", {})


class TestSendWelcomeMessages(unittest.IsolatedAsyncioTestCase):
    async def test_sends_messages_in_order_with_url_and_local_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "welcome.png"
            image_path.write_bytes(b"image")
            messages = [
                WelcomeMessage("First", "https://example.com/welcome.png"),
                WelcomeMessage("Second", "welcome.png"),
                WelcomeMessage("Third", None),
            ]
            user = AsyncMock()

            await send_welcome_messages(user, messages, temp_dir)

        self.assertEqual(user.send.await_count, 3)
        first_embed = user.send.await_args_list[0].kwargs["embed"]
        self.assertEqual(first_embed.image.url, "https://example.com/welcome.png")
        self.assertEqual(first_embed.description, "First")
        second_call = user.send.await_args_list[1]
        self.assertIsInstance(second_call.kwargs["file"], discord.File)
        self.assertEqual(
            second_call.kwargs["embed"].image.url,
            "attachment://welcome.png",
        )
        self.assertEqual(second_call.kwargs["embed"].description, "Second")
        self.assertEqual(user.send.await_args_list[2].kwargs, {"content": "Third"})

    async def test_rejects_local_image_outside_data_directory(self):
        user = AsyncMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "outside"):
                await send_welcome_messages(
                    user,
                    [WelcomeMessage("Welcome", "../outside.png")],
                    temp_dir,
                )

        user.send.assert_not_awaited()
