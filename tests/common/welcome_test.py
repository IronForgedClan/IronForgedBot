import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import discord

from ironforgedbot.common.welcome import (
    WelcomeMessage,
    format_welcome_content,
    load_welcome_messages,
    send_welcome_messages,
    send_welcome_messages_with_report,
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

    def test_replaces_channels_and_roles_placeholder_with_server_link(self):
        result = format_welcome_content(
            "Choose your channels: {{CHANNELS_AND_ROLES}}.", {}, guild_id=123
        )

        self.assertEqual(
            result,
            "Choose your channels: "
            "[Channels & Roles](https://discord.com/channels/123/customize-community).",
        )

    def test_raises_when_channels_and_roles_guild_is_not_configured(self):
        with self.assertRaisesRegex(ValueError, "GUILD_ID"):
            format_welcome_content("{{CHANNELS_AND_ROLES}}", {})

    @patch("ironforgedbot.common.welcome._resolve_welcome_emoji")
    def test_replaces_emoji_tokens_using_emoji_name(self, mock_resolve_emoji):
        mock_resolve_emoji.side_effect = lambda name: f"<:{name}:123>"

        result = format_welcome_content(
            "Balance: {{EMOJI:Ingot}} {{RULES_CHANNEL}}.",
            {"RULES_CHANNEL_ID": 456},
        )

        self.assertEqual(result, "Balance: <:Ingot:123> <#456>.")
        mock_resolve_emoji.assert_called_once_with("Ingot")

    @patch(
        "ironforgedbot.common.welcome._resolve_welcome_emoji", return_value=":Ingot:"
    )
    def test_uses_readable_fallback_for_missing_emoji(self, mock_resolve_emoji):
        result = format_welcome_content("{{EMOJI:Ingot}}", {})

        self.assertEqual(result, ":Ingot:")
        mock_resolve_emoji.assert_called_once_with("Ingot")


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

        self.assertEqual(user.send.await_count, 1)
        send_kwargs = user.send.await_args.kwargs
        embeds = send_kwargs["embeds"]
        self.assertEqual(len(embeds), 3)
        first_embed = embeds[0]
        self.assertEqual(first_embed.image.url, "https://example.com/welcome.png")
        self.assertEqual(first_embed.description, "First")
        second_embed = embeds[1]
        files = send_kwargs["files"]
        self.assertEqual(len(files), 1)
        self.assertIsInstance(files[0], discord.File)
        self.assertEqual(
            second_embed.image.url,
            f"attachment://{files[0].filename}",
        )
        self.assertEqual(second_embed.description, "Second")
        self.assertEqual(embeds[2].description, "Third")
        self.assertIsNone(embeds[2].image.url)

    async def test_batches_at_embed_limit(self):
        user = AsyncMock()
        messages = [WelcomeMessage(f"Section {index}") for index in range(11)]

        await send_welcome_messages(user, messages)

        self.assertEqual(user.send.await_count, 2)
        batches = [call.kwargs["embeds"] for call in user.send.await_args_list]
        self.assertEqual([len(batch) for batch in batches], [10, 1])
        self.assertEqual(
            [embed.description for batch in batches for embed in batch],
            [f"Section {index}" for index in range(11)],
        )

    async def test_splits_long_sections_and_batches_at_character_limit(self):
        user = AsyncMock()
        messages = [
            WelcomeMessage("A" * 5000),
            WelcomeMessage("B" * 1000),
            WelcomeMessage("C"),
        ]

        await send_welcome_messages(user, messages)

        self.assertEqual(user.send.await_count, 2)
        batches = [call.kwargs["embeds"] for call in user.send.await_args_list]
        self.assertEqual(
            [sum(len(embed.description or "") for embed in b) for b in batches],
            [6000, 1],
        )
        self.assertTrue(
            all(
                len(embed.description or "") <= 4096
                for batch in batches
                for embed in batch
            )
        )
        self.assertEqual(
            "".join(embed.description or "" for batch in batches for embed in batch),
            "A" * 5000 + "B" * 1000 + "C",
        )

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


class TestSendWelcomeMessagesWithReport(unittest.IsolatedAsyncioTestCase):
    async def test_reports_success_after_sending_messages(self):
        user = AsyncMock()
        report_channel = AsyncMock()

        with patch(
            "ironforgedbot.common.welcome.send_welcome_messages",
            new_callable=AsyncMock,
        ) as mock_send:
            await send_welcome_messages_with_report(user, report_channel)

        mock_send.assert_awaited_once_with(user)
        report_channel.send.assert_awaited_once()
        report_call = report_channel.send.await_args
        self.assertEqual(
            report_call.args[0],
            f"✅ Welcome messages sent to {user.mention}.",
        )
        self.assertFalse(report_call.kwargs["allowed_mentions"].users)

    async def test_reports_failure_and_reraises_send_error(self):
        user = AsyncMock()
        report_channel = AsyncMock()

        with patch(
            "ironforgedbot.common.welcome.send_welcome_messages",
            new_callable=AsyncMock,
            side_effect=ValueError("Welcome data is empty"),
        ) as mock_send:
            with self.assertRaisesRegex(ValueError, "Welcome data is empty"):
                await send_welcome_messages_with_report(user, report_channel)

        mock_send.assert_awaited_once_with(user)
        report_channel.send.assert_awaited_once()
        report_call = report_channel.send.await_args
        self.assertEqual(
            report_call.args[0],
            f"❌ Unable to send welcome messages to {user.mention}.\n"
            "Reason: ValueError: Welcome data is empty",
        )
        self.assertFalse(report_call.kwargs["allowed_mentions"].users)

    async def test_report_failure_does_not_replace_send_error(self):
        user = AsyncMock()
        report_channel = AsyncMock()
        report_channel.send.side_effect = discord.HTTPException(
            AsyncMock(), "Report channel unavailable"
        )

        with patch(
            "ironforgedbot.common.welcome.send_welcome_messages",
            new_callable=AsyncMock,
            side_effect=ValueError("Welcome data is empty"),
        ):
            with self.assertRaisesRegex(ValueError, "Welcome data is empty"):
                await send_welcome_messages_with_report(user, report_channel)

    async def test_report_failure_does_not_fail_successful_send(self):
        user = AsyncMock()
        report_channel = AsyncMock()
        report_channel.send.side_effect = discord.HTTPException(
            AsyncMock(), "Report channel unavailable"
        )

        with patch(
            "ironforgedbot.common.welcome.send_welcome_messages",
            new_callable=AsyncMock,
        ) as mock_send:
            await send_welcome_messages_with_report(user, report_channel)

        mock_send.assert_awaited_once_with(user)
