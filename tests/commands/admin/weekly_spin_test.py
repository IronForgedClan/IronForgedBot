import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from ironforgedbot.commands.admin import weekly_spin
from ironforgedbot.commands.admin.weekly_spin import (
    RerollPaymentView,
    WeeklySpinView,
    _build_history_line,
    _build_pending_content,
    _build_post_content,
    _check_reroll_rate_limit,
    post_weekly_spin_result,
)


def _make_role(name: str):
    role = MagicMock(spec=discord.Role)
    role.name = name
    return role


def _make_interaction(
    *,
    user_id: int = 999,
    role_names: list[str] | None = None,
):
    role_names = role_names if role_names is not None else ["Member"]
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id
    interaction.user.mention = f"<@{user_id}>"
    interaction.user.roles = [_make_role(n) for n in role_names]
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.original_response = AsyncMock()
    interaction.delete_original_response = AsyncMock()
    interaction.guild = MagicMock(spec=discord.Guild)
    return interaction


def _invoke_callback(view, callback_name: str, interaction, button):
    """Call the class-level callback by name, bypassing View's _init_children
    shadowing of the instance attribute."""
    callback = getattr(type(view), callback_name)
    return callback(view, interaction, button)


class TestCheckRerollRateLimit(unittest.TestCase):
    def setUp(self):
        weekly_spin._recent_rerolls.clear()

    def test_allows_under_limit(self):
        for _ in range(9):
            allowed, wait = _check_reroll_rate_limit(1, "sotw", now=1000.0)
            self.assertTrue(allowed)
            self.assertEqual(wait, 0)

    def test_denies_at_limit(self):
        for _ in range(10):
            _check_reroll_rate_limit(1, "sotw", now=1000.0)
        allowed, wait = _check_reroll_rate_limit(1, "sotw", now=1001.0)
        self.assertFalse(allowed)
        self.assertGreater(wait, 0)

    def test_recovers_after_window(self):
        for _ in range(10):
            _check_reroll_rate_limit(1, "sotw", now=1000.0)
        allowed, _ = _check_reroll_rate_limit(1, "sotw", now=1000.0 + 3601.0)
        self.assertTrue(allowed)

    def test_separates_per_kind(self):
        for _ in range(10):
            _check_reroll_rate_limit(1, "sotw", now=1000.0)
        sotw_blocked, _ = _check_reroll_rate_limit(1, "sotw", now=1001.0)
        self.assertFalse(sotw_blocked)
        botw_allowed, _ = _check_reroll_rate_limit(1, "botw", now=1001.0)
        self.assertTrue(botw_allowed)

    def test_separates_per_user(self):
        for _ in range(10):
            _check_reroll_rate_limit(1, "sotw", now=1000.0)
        blocked, _ = _check_reroll_rate_limit(1, "sotw", now=1001.0)
        self.assertFalse(blocked)
        allowed, _ = _check_reroll_rate_limit(2, "sotw", now=1001.0)
        self.assertTrue(allowed)


class TestBuildPostContent(unittest.TestCase):
    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    def test_sotw_no_history(self, mock_data, mock_find_emoji):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"
        self.assertEqual(
            _build_post_content("sotw", "Agility", []),
            "# Next SOTW is ||\U0001f3c3 Agility||",
        )

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    def test_botw_no_history(self, mock_data, mock_find_emoji):
        mock_data.BOSSES = [{"name": "Zulrah", "emoji_key": "zulrah"}]
        mock_find_emoji.return_value = "\U0001f40d"
        self.assertEqual(
            _build_post_content("botw", "Zulrah", []),
            "# Next BOTW is ||\U0001f40d Zulrah||",
        )

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    def test_sotw_with_history(self, mock_data, mock_find_emoji):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"
        history = ["~~Crafting~~ rerolled by @User1"]
        expected = (
            "# Next SOTW is ||\U0001f3c3 Agility||\n"
            "- ~~Crafting~~ rerolled by @User1"
        )
        self.assertEqual(_build_post_content("sotw", "Agility", history), expected)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    def test_botw_with_history_grows_lines(self, mock_data, mock_find_emoji):
        mock_data.BOSSES = [{"name": "Zulrah", "emoji_key": "zulrah"}]
        mock_find_emoji.return_value = "\U0001f40d"
        history = [
            "~~Crafting~~ rerolled by @User1",
            "~~Agility~~ rerolled by @User2",
        ]
        expected = (
            "# Next BOTW is ||\U0001f40d Zulrah||\n"
            "- ~~Crafting~~ rerolled by @User1\n"
            "- ~~Agility~~ rerolled by @User2"
        )
        self.assertEqual(_build_post_content("botw", "Zulrah", history), expected)

    def test_blank_line_always_before_footer(self):
        with patch(
            "ironforgedbot.commands.admin.weekly_spin.data",
            SKILLS=[{"name": "Agility", "emoji_key": "agility"}],
        ):
            with patch("ironforgedbot.commands.admin.weekly_spin.find_emoji") as me:
                me.return_value = "\U0001f3c3"
                result = _build_post_content(
                    "sotw", "Agility", [], reroll_close_ts=1735612800
                )
        self.assertIn("\n\n-# Re-roll window closes", result)

    def test_history_renders_as_bullet_list(self):
        with patch(
            "ironforgedbot.commands.admin.weekly_spin.data",
            SKILLS=[{"name": "Agility", "emoji_key": "agility"}],
        ):
            with patch("ironforgedbot.commands.admin.weekly_spin.find_emoji") as me:
                me.return_value = "\U0001f3c3"
                result = _build_post_content(
                    "sotw", "Agility", ["~~X~~ rerolled by @U"], reroll_close_ts=1
                )
        self.assertIn("- ~~X~~ rerolled by @U", result)

    def test_no_blank_line_when_no_footer(self):
        with patch(
            "ironforgedbot.commands.admin.weekly_spin.data",
            SKILLS=[{"name": "Agility", "emoji_key": "agility"}],
        ):
            with patch("ironforgedbot.commands.admin.weekly_spin.find_emoji") as me:
                me.return_value = "\U0001f3c3"
                result = _build_post_content(
                    "sotw", "Agility", ["~~X~~ rerolled by @U"]
                )
        self.assertNotIn("\n\n-#", result)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    def test_footer_line_appended_with_close_ts(self, mock_data, mock_find_emoji):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"
        result = _build_post_content("sotw", "Agility", [], reroll_close_ts=1735612800)
        self.assertTrue(result.endswith("-# Re-roll window closes <t:1735612800:R>."))

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    def test_no_footer_when_reroll_close_ts_none(self, mock_data, mock_find_emoji):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"
        result = _build_post_content("sotw", "Agility", [])
        self.assertNotIn("-# Re-roll window", result)


class TestBuildPendingContent(unittest.TestCase):
    def test_pending_header_signals_incoming_result(self):
        self.assertEqual(_build_pending_content("sotw", []), "# Next SOTW is...")

    def test_pending_with_history_includes_history_lines(self):
        history = ["~~Crafting~~ rerolled by @User1"]
        self.assertEqual(
            _build_pending_content("sotw", history),
            "# Next SOTW is...\n- ~~Crafting~~ rerolled by @User1",
        )

    def test_pending_with_footer_includes_footer(self):
        result = _build_pending_content("sotw", [], reroll_close_ts=1735612800)
        self.assertTrue(result.endswith("-# Re-roll window closes <t:1735612800:R>."))

    def test_pending_blank_line_before_footer(self):
        result = _build_pending_content("sotw", [], reroll_close_ts=1735612800)
        self.assertIn("\n\n-# Re-roll window closes", result)

    def test_pending_validates_kind(self):
        with self.assertRaises(ValueError):
            _build_pending_content("weekly", [])


class TestBuildHistoryLine(unittest.TestCase):
    def test_format(self):
        self.assertEqual(
            _build_history_line("Crafting", "@User1"),
            "~~Crafting~~ rerolled by @User1",
        )

    def test_empty_previous_winner(self):
        self.assertEqual(
            _build_history_line("", "@User1"),
            "~~~~ rerolled by @User1",
        )

    def test_grouped_botw_winner_is_fully_struck(self):
        self.assertEqual(
            _build_history_line("Callisto or Artio", "@User1"),
            "~~Callisto or Artio~~ rerolled by @User1",
        )


class TestPostWeeklySpinResult(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.target = AsyncMock(spec=discord.TextChannel)
        self.sent_message = MagicMock(spec=discord.Message)
        self.sent_message.add_reaction = AsyncMock()
        self.target.send = AsyncMock(return_value=self.sent_message)
        self.file = MagicMock(spec=discord.File)
        self.options = ["opt1", "opt2", "opt3"]

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_sends_with_view_attached(self, mock_data, mock_find_emoji):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        msg = await post_weekly_spin_result(
            self.target, "sotw", self.options, self.file, "Agility"
        )

        self.assertIs(msg, self.sent_message)
        call_kwargs = self.target.send.call_args.kwargs
        self.assertIn("view", call_kwargs)
        view = call_kwargs["view"]
        self.assertIsInstance(view, WeeklySpinView)
        self.assertEqual(view.kind, "sotw")
        self.assertEqual(view.options, self.options)
        self.assertIs(view.target_message, self.sent_message)

    @patch("ironforgedbot.commands.admin.weekly_spin.time")
    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_sends_correct_content(self, mock_data, mock_find_emoji, mock_time):
        mock_time.time.return_value = 1_000_000.0
        mock_data.BOSSES = [{"name": "Zulrah", "emoji_key": "zulrah"}]
        mock_find_emoji.return_value = "\U0001f40d"

        await post_weekly_spin_result(
            self.target, "botw", self.options, self.file, "Zulrah"
        )

        self.target.send.assert_called_once()
        content = self.target.send.call_args.kwargs["content"]
        expected_footer = "-# Re-roll window closes <t:1086400:R>."
        self.assertEqual(
            content,
            f"# Next BOTW is...\n\n{expected_footer}",
        )

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_adds_thumb_reactions_sequentially(self, mock_data, mock_find_emoji):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        await post_weekly_spin_result(
            self.target, "sotw", self.options, self.file, "Agility"
        )

        self.assertEqual(self.sent_message.add_reaction.call_count, 2)
        calls = self.sent_message.add_reaction.call_args_list
        self.assertEqual(calls[0].args[0], "\U0001f44d")
        self.assertEqual(calls[1].args[0], "\U0001f44e")

    @patch("ironforgedbot.commands.admin.weekly_spin.time")
    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_post_weekly_spin_botw_handles_grouped_winner(
        self, mock_data, mock_find_emoji, mock_time
    ):
        mock_time.time.return_value = 1_000_000.0
        mock_data.BOSSES = [{"name": "Callisto", "emoji_key": "callisto"}]
        mock_find_emoji.return_value = "\U0001f98a"

        await post_weekly_spin_result(
            self.target, "botw", self.options, self.file, "Callisto or Artio"
        )

        content = self.target.send.call_args.kwargs["content"]
        self.assertTrue(content.startswith("# Next BOTW is...\n\n-# "))
        mock_find_emoji.assert_not_called()

    @patch("ironforgedbot.commands.admin.weekly_spin.time")
    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_post_weekly_spin_sotw_fallback_emoji_on_unknown_winner(
        self, mock_data, mock_find_emoji, mock_time
    ):
        mock_time.time.return_value = 1_000_000.0
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        await post_weekly_spin_result(
            self.target, "sotw", self.options, self.file, "UnknownSkill"
        )

        content = self.target.send.call_args.kwargs["content"]
        self.assertTrue(content.startswith("# Next SOTW is...\n\n-# "))
        mock_find_emoji.assert_not_called()

    @patch("ironforgedbot.commands.admin.weekly_spin.time")
    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_post_weekly_spin_botw_fallback_emoji_on_unknown_winner(
        self, mock_data, mock_find_emoji, mock_time
    ):
        mock_time.time.return_value = 1_000_000.0
        mock_data.BOSSES = [{"name": "Zulrah", "emoji_key": "zulrah"}]
        mock_find_emoji.return_value = "\U0001f40d"

        await post_weekly_spin_result(
            self.target, "botw", self.options, self.file, "UnknownBoss"
        )

        content = self.target.send.call_args.kwargs["content"]
        self.assertTrue(content.startswith("# Next BOTW is...\n\n-# "))
        mock_find_emoji.assert_not_called()

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_post_weekly_spin_returns_sent_message(
        self, mock_data, mock_find_emoji
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        result = await post_weekly_spin_result(
            self.target, "sotw", self.options, self.file, "Agility"
        )
        self.assertIs(result, self.sent_message)

    async def test_post_weekly_spin_raises_on_unknown_kind(self):
        with self.assertRaises(ValueError):
            await post_weekly_spin_result(
                self.target, "weekly", self.options, self.file, "Anything"
            )


class TestWeeklySpinView(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.target_message = MagicMock(spec=discord.Message)
        self.target_message.edit = AsyncMock()
        self.view = WeeklySpinView(
            options=["a", "b", "c"], kind="sotw", target_message=self.target_message
        )
        # Tests in this class assume the reveal has completed (i.e. the
        # button is clickable in the steady state). Tests for the pending
        # state explicitly flip _reroll_unlocked back to False.
        self.view._reroll_unlocked = True
        self.view._apply_button_state()

    async def test_interaction_check_denies_non_member(self):
        interaction = _make_interaction(role_names=["SomeOtherRole"])
        result = await self.view.interaction_check(interaction)
        self.assertFalse(result)
        interaction.response.send_message.assert_called_once()
        self.assertIn(
            "Member role required",
            interaction.response.send_message.call_args.args[0],
        )

    async def test_interaction_check_allows_member(self):
        interaction = _make_interaction(role_names=["Member"])
        result = await self.view.interaction_check(interaction)
        self.assertTrue(result)
        interaction.response.send_message.assert_not_called()

    @patch("ironforgedbot.commands.admin.weekly_spin.build_payment_embed")
    @patch("ironforgedbot.commands.admin.weekly_spin.MemberService")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    @patch("ironforgedbot.commands.admin.weekly_spin._check_reroll_rate_limit")
    async def test_reroll_opens_payment_confirmation_with_canonical_embed(
        self, mock_rate_limit, mock_db, mock_member_service_cls, mock_build_embed
    ):
        mock_rate_limit.return_value = (True, 0)
        mock_member = MagicMock()
        mock_member.ingots = 9999
        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=mock_member
        )
        mock_member_service_cls.return_value = mock_member_service
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session

        mock_embed = MagicMock(spec=discord.Embed)
        mock_build_embed.return_value = mock_embed
        sent_message = MagicMock(spec=discord.Message)
        interaction = _make_interaction(role_names=["Member"])
        interaction.original_response = AsyncMock()
        interaction.followup.send = AsyncMock(return_value=sent_message)
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "reroll_button", interaction, button)

        mock_build_embed.assert_called_once()
        kwargs = mock_build_embed.call_args.kwargs
        self.assertEqual(kwargs["cost"], 2500)
        self.assertEqual(kwargs["user_balance"], 9999)
        self.assertEqual(kwargs["title"], "\U0001f4b0 Re-roll Weekly Spin")

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.response.send_message.assert_not_called()
        interaction.edit_original_response.assert_not_called()
        interaction.followup.send.assert_called_once()
        followup_kwargs = interaction.followup.send.call_args.kwargs
        self.assertTrue(followup_kwargs["ephemeral"])
        self.assertIn("view", followup_kwargs)
        sent_view = followup_kwargs["view"]
        self.assertIsInstance(sent_view, RerollPaymentView)
        self.assertIs(followup_kwargs["embed"], mock_embed)
        self.assertIs(sent_view.message, sent_message)

    @patch("ironforgedbot.commands.admin.weekly_spin.build_payment_embed")
    @patch("ironforgedbot.commands.admin.weekly_spin.MemberService")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    @patch("ironforgedbot.commands.admin.weekly_spin._check_reroll_rate_limit")
    async def test_reroll_payment_embed_is_ephemeral(
        self, mock_rate_limit, mock_db, mock_member_service_cls, mock_build_embed
    ):
        mock_rate_limit.return_value = (True, 0)
        mock_member_service_cls.return_value = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_build_embed.return_value = MagicMock(spec=discord.Embed)

        interaction = _make_interaction(role_names=["Member"])
        interaction.followup.send = AsyncMock(
            return_value=MagicMock(spec=discord.Message)
        )
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "reroll_button", interaction, button)

        self.assertTrue(interaction.followup.send.call_args.kwargs["ephemeral"])
        interaction.edit_original_response.assert_not_called()

    @patch("ironforgedbot.commands.admin.weekly_spin.build_payment_embed")
    @patch("ironforgedbot.commands.admin.weekly_spin.MemberService")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    @patch("ironforgedbot.commands.admin.weekly_spin._check_reroll_rate_limit")
    async def test_reroll_defers_before_slow_db_lookup(
        self, mock_rate_limit, mock_db, mock_member_service_cls, mock_build_embed
    ):
        mock_rate_limit.return_value = (True, 0)
        call_order: list[str] = []

        def record_defer(*args, **kwargs):
            call_order.append("defer")

        async def record_get_member(*args, **kwargs):
            call_order.append("get_member")
            mock_member = MagicMock()
            mock_member.ingots = 1000
            return mock_member

        interaction = _make_interaction(role_names=["Member"])
        interaction.response.defer.side_effect = record_defer
        interaction.original_response = AsyncMock()
        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id = record_get_member
        mock_member_service_cls.return_value = mock_member_service
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_build_embed.return_value = MagicMock(spec=discord.Embed)

        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "reroll_button", interaction, button)

        self.assertEqual(call_order, ["defer", "get_member"])

    @patch("ironforgedbot.commands.admin.weekly_spin.build_payment_embed")
    @patch("ironforgedbot.commands.admin.weekly_spin.MemberService")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    @patch("ironforgedbot.commands.admin.weekly_spin._check_reroll_rate_limit")
    async def test_reroll_locks_view_and_disables_buttons(
        self, mock_rate_limit, mock_db, mock_member_service_cls, mock_build_embed
    ):
        mock_rate_limit.return_value = (True, 0)
        mock_member_service_cls.return_value = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_build_embed.return_value = MagicMock(spec=discord.Embed)

        interaction = _make_interaction(role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "reroll_button", interaction, button)

        self.assertTrue(self.view.reroll_locked)
        self.assertTrue(self.view._reroll_button.disabled)
        self.target_message.edit.assert_called_once()
        edit_kwargs = self.target_message.edit.call_args.kwargs
        self.assertIn("view", edit_kwargs)

    async def test_interaction_check_denies_when_locked(self):
        self.view.reroll_locked = True
        interaction = _make_interaction(role_names=["Member"])
        result = await self.view.interaction_check(interaction)
        self.assertFalse(result)
        interaction.response.send_message.assert_called_once()
        self.assertIn(
            "in progress",
            interaction.response.send_message.call_args.args[0],
        )

    @patch("ironforgedbot.commands.admin.weekly_spin._check_reroll_rate_limit")
    async def test_reroll_at_cap_denied(self, mock_rate_limit):
        mock_rate_limit.return_value = (False, 1800)
        interaction = _make_interaction(role_names=["Member"])
        interaction.followup.send = AsyncMock(
            return_value=MagicMock(spec=discord.Message)
        )
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "reroll_button", interaction, button)

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.response.send_message.assert_not_called()
        interaction.edit_original_response.assert_not_called()
        interaction.followup.send.assert_called_once()
        followup_kwargs = interaction.followup.send.call_args.kwargs
        self.assertTrue(followup_kwargs["ephemeral"])
        content = followup_kwargs.get("content", "")
        self.assertIn("cap reached", content.lower())
        self.assertIn("30", content)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_on_timeout_disables_buttons_and_strips_footer(
        self, mock_data, mock_find_emoji
    ):
        mock_data.SKILLS = [{"name": "Zulrah", "emoji_key": "zulrah"}]
        mock_find_emoji.return_value = "\U0001f40d"
        self.view.target_message = self.target_message
        self.view.current_winner = "Zulrah"

        await self.view.on_timeout()

        self.assertNotIn(self.view._reroll_button, self.view.children)
        self.assertTrue(self.view._timed_out)
        self.target_message.edit.assert_called_once()
        edit_kwargs = self.target_message.edit.call_args.kwargs
        self.assertIn("content", edit_kwargs)
        self.assertNotIn("-# Re-roll window", edit_kwargs["content"])
        self.assertIn("# Next SOTW is ||\U0001f40d Zulrah||", edit_kwargs["content"])

    async def test_on_timeout_without_current_winner_skips_content_edit(self):
        self.view.target_message = self.target_message

        await self.view.on_timeout()

        self.assertNotIn(self.view._reroll_button, self.view.children)
        self.target_message.edit.assert_called_once()
        edit_kwargs = self.target_message.edit.call_args.kwargs
        self.assertNotIn("content", edit_kwargs)
        self.assertEqual(edit_kwargs.get("view"), None)

    def test_initial_view_button_disabled_pending_reveal(self):
        fresh_view = WeeklySpinView(options=["a"], kind="sotw", target_message=None)
        self.assertFalse(fresh_view._reroll_unlocked)
        self.assertFalse(fresh_view.reroll_locked)
        self.assertTrue(fresh_view.children[0].disabled)

    async def test_interaction_check_blocks_while_pending_reveal(self):
        # Fresh view = _reroll_unlocked=False.
        fresh_view = WeeklySpinView(
            options=["a"], kind="sotw", target_message=self.target_message
        )
        interaction = _make_interaction(role_names=["Member"])
        result = await fresh_view.interaction_check(interaction)
        self.assertFalse(result)
        interaction.response.send_message.assert_called_once()
        self.assertIn(
            "pending reveal",
            interaction.response.send_message.call_args.args[0],
        )

    def test_apply_button_state_enables_when_unlocked(self):
        self.view._reroll_button.disabled = True
        self.view._reroll_unlocked = True
        self.view.reroll_locked = False
        self.view._lock_window_active = False
        self.view._is_locked = False
        self.view._apply_button_state()
        self.assertFalse(self.view._reroll_button.disabled)

    def test_apply_button_state_disables_while_concurrent_locked(self):
        self.view._reroll_button.disabled = False
        self.view._reroll_unlocked = True
        self.view.reroll_locked = True
        self.view._apply_button_state()
        self.assertTrue(self.view._reroll_button.disabled)

    def test_reroll_button_disabled_during_lock_window(self):
        self.view._lock_window_active = True
        self.view._apply_button_state()
        self.assertTrue(self.view._reroll_button.disabled)

    def test_reroll_button_disabled_when_locked(self):
        self.view._is_locked = True
        self.view._apply_button_state()
        self.assertTrue(self.view._reroll_button.disabled)

    def test_lock_buttons_added_only_during_lock_window(self):
        self.assertNotIn(self.view._lock_button, self.view.children)
        self.assertNotIn(self.view._dont_lock_button, self.view.children)

        self.view._lock_window_active = True
        self.view.add_item(self.view._lock_button)
        self.view.add_item(self.view._dont_lock_button)
        self.assertIn(self.view._lock_button, self.view.children)
        self.assertIn(self.view._dont_lock_button, self.view.children)

    def test_initial_view_has_no_lock_window_state(self):
        fresh = WeeklySpinView(options=["a"], kind="sotw", target_message=None)
        self.assertFalse(fresh._lock_window_active)
        self.assertFalse(fresh._is_locked)
        self.assertIsNone(fresh._lock_window_user_id)
        # _reroll_unlocked starts False (reveal task flips it later), so the
        # Re-roll button is correctly disabled at construction time.
        self.assertTrue(fresh._reroll_button.disabled)

    async def test_interaction_check_denies_other_user_during_lock_window(self):
        self.view._lock_window_active = True
        self.view._lock_window_user_id = 999
        interaction = _make_interaction(role_names=["Member"], user_id=42)
        result = await self.view.interaction_check(interaction)
        self.assertFalse(result)
        interaction.response.send_message.assert_called_once()
        self.assertIn(
            "who rerolled",
            interaction.response.send_message.call_args.args[0],
        )

    async def test_interaction_check_allows_rigger_during_lock_window(self):
        self.view._lock_window_active = True
        self.view._lock_window_user_id = 999
        interaction = _make_interaction(role_names=["Member"], user_id=999)
        result = await self.view.interaction_check(interaction)
        self.assertTrue(result)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_build_lock_window_content_uses_relative_timestamp(
        self, mock_data, mock_find_emoji
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        content = weekly_spin._build_lock_window_content(
            kind="sotw",
            winner="Agility",
            history_lines=["~~Old~~ rerolled by <@42>"],
            user_mention="<@42>",
            lock_close_ts=1234567890,
            reroll_close_ts=1234570000,
        )
        self.assertIn("# Next SOTW is ||\U0001f3c3 Agility||", content)
        self.assertIn("<@42>", content)
        self.assertIn("<t:1234567890:R>", content)
        self.assertIn("lock before re-rolls", content)
        self.assertIn("Re-roll window closes <t:1234570000:R>", content)

    def test_build_locked_content_appends_lock_emoji(self):
        with patch(
            "ironforgedbot.commands.admin.weekly_spin.find_emoji",
            return_value="\U0001f3c3",
        ), patch(
            "ironforgedbot.commands.admin.weekly_spin.data",
            MagicMock(SKILLS=[{"name": "Agility", "emoji_key": "agility"}]),
        ):
            content = weekly_spin._build_locked_content(
                kind="sotw",
                winner="Agility",
                history_lines=["~~Old~~ rerolled by <@42>", "<@42> \U0001f512"],
            )
        self.assertIn("\U0001f3c3 Agility|| \U0001f512", content)
        self.assertNotIn("Re-roll window closes", content)
        self.assertIn("~~Old~~ rerolled by <@42>", content)

    def test_build_lock_decision_line_uses_lock_emoji_when_locked(self):
        line = weekly_spin._build_lock_decision_line("<@42>", locked=True)
        self.assertEqual(line, "<@42> \U0001f512")

    def test_build_lock_decision_line_uses_unlock_emoji_when_unlocked(self):
        line = weekly_spin._build_lock_decision_line("<@42>", locked=False)
        self.assertEqual(line, "<@42> \U0001f513")

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_open_lock_window_sets_state_and_edits_message(
        self, mock_data, mock_find_emoji
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)

        self.assertTrue(self.view._lock_window_active)
        self.assertEqual(self.view._lock_window_user_id, 999)
        self.assertGreater(self.view._lock_window_end_ts, 0)
        self.assertIn(self.view._lock_button, self.view.children)
        self.assertIn(self.view._dont_lock_button, self.view.children)
        self.assertTrue(self.view._reroll_button.disabled)
        self.target_message.edit.assert_called()

        # Find the lock-window edit call (the one whose content mentions the
        # countdown footer) and assert it includes the relative timestamp.
        lock_edit_call = next(
            (
                c
                for c in self.target_message.edit.call_args_list
                if "content" in c.kwargs
                and "<t:" in c.kwargs["content"]
                and "lock before re-rolls" in c.kwargs["content"]
            ),
            None,
        )
        self.assertIsNotNone(lock_edit_call, "expected lock-window content edit")
        self.assertIn("<@999>", lock_edit_call.kwargs["content"])

        # Lock-window task scheduled and not yet done
        self.assertIsNotNone(self.view._lock_window_task)
        self.assertFalse(self.view._lock_window_task.done())

        # Clean up the timer so the test event loop can exit
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_close_lock_window_as_locked_removes_all_buttons_and_sets_state(
        self, mock_data, mock_find_emoji
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        await self.view._close_lock_window_as_locked()

        self.assertTrue(self.view._is_locked)
        self.assertFalse(self.view._lock_window_active)
        self.assertNotIn(self.view._reroll_button, self.view.children)
        self.assertNotIn(self.view._lock_button, self.view.children)
        self.assertNotIn(self.view._dont_lock_button, self.view.children)
        self.assertTrue(
            any(
                "\U0001f512" in line and "<@999>" in line
                for line in self.view.history_lines
            ),
            "expected lock-decision history line",
        )

        final_edit = self.target_message.edit.call_args_list[-1]
        self.assertIn("content", final_edit.kwargs)
        self.assertIn("\U0001f512", final_edit.kwargs["content"])

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_close_lock_window_as_open_appends_unlock_history_and_reenables_reroll(
        self, mock_data, mock_find_emoji
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        await self.view._close_lock_window_as_open(
            message=self.target_message,
            add_history_line=True,
        )

        self.assertFalse(self.view._lock_window_active)
        self.assertFalse(self.view._is_locked)
        self.assertNotIn(self.view._lock_button, self.view.children)
        self.assertNotIn(self.view._dont_lock_button, self.view.children)
        self.assertFalse(self.view._reroll_button.disabled)
        self.assertTrue(
            any(
                "\U0001f513" in line and "<@999>" in line
                for line in self.view.history_lines
            ),
            "expected unlock-decision history line",
        )

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_close_lock_window_as_open_silent_when_no_history_line(
        self, mock_data, mock_find_emoji
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        history_before = list(self.view.history_lines)
        await self.view._close_lock_window_as_open(
            message=self.target_message,
            add_history_line=False,
        )
        self.assertEqual(self.view.history_lines, history_before)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_lock_button_charges_10000_ingots(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_build_spin_gif,
        mock_data,
        mock_find_emoji,
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        success = MagicMock()
        success.status = True
        success.new_total = 5000
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success)
        mock_create_ingot_service.return_value = mock_service

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        interaction = _make_interaction(user_id=999, role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "lock_button", interaction, button)

        mock_service.try_remove_ingots.assert_called_once()
        call_args = mock_service.try_remove_ingots.call_args
        self.assertEqual(call_args.args[0], 999)
        self.assertEqual(call_args.args[1], -10000)
        self.assertIn("Lock weekly spin: SOTW", call_args.args[3])

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_lock_insufficient_funds_keeps_window_open(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_data,
        mock_find_emoji,
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        fail = MagicMock()
        fail.status = False
        fail.new_total = 100
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=fail)
        mock_create_ingot_service.return_value = mock_service

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        interaction = _make_interaction(user_id=999, role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "lock_button", interaction, button)

        self.assertTrue(self.view._lock_window_active)
        self.assertFalse(self.view._is_locked)
        self.assertIn(self.view._lock_button, self.view.children)
        self.assertIn(self.view._dont_lock_button, self.view.children)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_dont_lock_button_does_not_charge_ingots(
        self, mock_data, mock_find_emoji
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        with patch("ironforgedbot.commands.admin.weekly_spin.db") as mock_db, patch(
            "ironforgedbot.commands.admin.weekly_spin.create_ingot_service"
        ) as mock_create:
            interaction = _make_interaction(user_id=999, role_names=["Member"])
            button = MagicMock(spec=discord.ui.Button)
            await _invoke_callback(self.view, "dont_lock_button", interaction, button)
            mock_db.get_session.assert_not_called()
            mock_create.assert_not_called()

        self.assertFalse(self.view._lock_window_active)
        self.assertFalse(self.view._is_locked)
        self.assertNotIn(self.view._lock_button, self.view.children)
        self.assertNotIn(self.view._dont_lock_button, self.view.children)
        self.assertFalse(self.view._reroll_button.disabled)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_lock_button_does_not_delete_spin_post(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_data,
        mock_find_emoji,
    ):
        """Regression: defer() on a component interaction is type 6
        (deferred_message_update), so ``original_response`` resolves to the
        message that triggered the interaction (the spin post itself).
        Calling ``delete_original_response`` after it deletes the spin post
        out of the channel — the rigger must still see their locked post."""
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        success = MagicMock()
        success.status = True
        success.new_total = 5000
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success)
        mock_create_ingot_service.return_value = mock_service

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        self.target_message.delete = AsyncMock()

        interaction = _make_interaction(user_id=999, role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "lock_button", interaction, button)

        self.target_message.delete.assert_not_called()
        interaction.delete_original_response.assert_not_called()
        final_edit = self.target_message.edit.call_args_list[-1]
        self.assertIsNone(final_edit.kwargs.get("view"))
        self.assertIn("\U0001f512", final_edit.kwargs["content"])

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_lock_insufficient_funds_does_not_delete_spin_post(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_data,
        mock_find_emoji,
    ):
        """Regression: the failed-debit branch must also avoid
        ``delete_original_response`` so a rejected lock attempt does not
        silently remove the spin post from the channel."""
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        fail = MagicMock()
        fail.status = False
        fail.new_total = 100
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=fail)
        mock_create_ingot_service.return_value = mock_service

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        self.target_message.delete = AsyncMock()

        interaction = _make_interaction(user_id=999, role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "lock_button", interaction, button)

        self.target_message.delete.assert_not_called()
        interaction.delete_original_response.assert_not_called()
        self.assertTrue(self.view._lock_window_active)
        self.assertFalse(self.view._is_locked)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_dont_lock_button_does_not_delete_spin_post(
        self, mock_data, mock_find_emoji
    ):
        """Regression: same as the lock branch — ``delete_original_response``
        after a default ``defer()`` on a component button would wipe the spin
        post instead of clearing a non-existent loading state."""
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        self.target_message.delete = AsyncMock()

        interaction = _make_interaction(user_id=999, role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "dont_lock_button", interaction, button)

        self.target_message.delete.assert_not_called()
        interaction.delete_original_response.assert_not_called()
        final_edit = self.target_message.edit.call_args_list[-1]
        self.assertIn("# Next SOTW is ||", final_edit.kwargs["content"])
        self.assertIn("\U0001f513", final_edit.kwargs["content"])
        self.assertIn("<@999>", final_edit.kwargs["content"])

    async def test_lock_button_rejects_non_rigger(self):
        with patch(
            "ironforgedbot.commands.admin.weekly_spin.find_emoji",
            return_value="\U0001f3c3",
        ), patch(
            "ironforgedbot.commands.admin.weekly_spin.data",
            MagicMock(SKILLS=[{"name": "Agility", "emoji_key": "agility"}]),
        ):
            self.view.current_winner = "Agility"
            await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        other = _make_interaction(user_id=42, role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "lock_button", other, button)

        other.response.send_message.assert_called_once()
        self.assertIn(
            "who rerolled",
            other.response.send_message.call_args.args[0],
        )
        self.assertTrue(self.view._lock_window_active)

    async def test_dont_lock_button_rejects_non_rigger(self):
        with patch(
            "ironforgedbot.commands.admin.weekly_spin.find_emoji",
            return_value="\U0001f3c3",
        ), patch(
            "ironforgedbot.commands.admin.weekly_spin.data",
            MagicMock(SKILLS=[{"name": "Agility", "emoji_key": "agility"}]),
        ):
            self.view.current_winner = "Agility"
            await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        other = _make_interaction(user_id=42, role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "dont_lock_button", other, button)

        other.response.send_message.assert_called_once()
        self.assertIn(
            "who rerolled",
            other.response.send_message.call_args.args[0],
        )
        self.assertTrue(self.view._lock_window_active)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_lock_button_double_click_only_charges_once(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_data,
        mock_find_emoji,
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        success = MagicMock()
        success.status = True
        success.new_total = 5000
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success)
        mock_create_ingot_service.return_value = mock_service

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        interaction1 = _make_interaction(user_id=999, role_names=["Member"])
        interaction2 = _make_interaction(user_id=999, role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)

        await asyncio.gather(
            _invoke_callback(self.view, "lock_button", interaction1, button),
            _invoke_callback(self.view, "lock_button", interaction2, button),
        )

        mock_service.try_remove_ingots.assert_called_once()

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_lock_window_timer_times_out_reenables_reroll(
        self, mock_data, mock_find_emoji
    ):
        """Bypass real sleep; assert the post-timer state."""
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        # Drive the close path directly (matches what the timer does on
        # timeout). No history line because the user did not decide.
        await self.view._close_lock_window_as_open(
            message=self.target_message,
            add_history_line=False,
        )

        self.assertFalse(self.view._lock_window_active)
        self.assertFalse(self.view._is_locked)
        self.assertNotIn(self.view._lock_button, self.view.children)
        self.assertNotIn(self.view._dont_lock_button, self.view.children)
        self.assertFalse(self.view._reroll_button.disabled)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_on_timeout_locked_state_uses_locked_content(
        self, mock_data, mock_find_emoji
    ):
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        self.view.current_winner = "Agility"
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        await self.view._close_lock_window_as_locked()

        self.target_message.edit.reset_mock()
        await self.view.on_timeout()

        self.assertTrue(self.view._timed_out)
        edit_kwargs = self.target_message.edit.call_args.kwargs
        self.assertIn("content", edit_kwargs)
        self.assertNotIn("Re-roll window closes", edit_kwargs["content"])
        self.assertIn("\U0001f512", edit_kwargs["content"])

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    @patch("ironforgedbot.commands.admin.weekly_spin.MemberService")
    @patch("ironforgedbot.commands.admin.weekly_spin._check_reroll_rate_limit")
    async def test_reroll_success_opens_lock_window(
        self,
        mock_rate_limit,
        mock_member_service_cls,
        mock_db,
        mock_create_ingot_service,
        mock_build_spin_gif,
        mock_data,
        mock_find_emoji,
    ):
        mock_rate_limit.return_value = (True, 0)
        mock_data.SKILLS = [{"name": "NewSkill", "emoji_key": "newskill"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        success = MagicMock()
        success.status = True
        success.new_total = 5000
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success)
        mock_create_ingot_service.return_value = mock_service

        mock_member = MagicMock()
        mock_member.ingots = 99999
        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=mock_member
        )
        mock_member_service_cls.return_value = mock_member_service

        new_file = MagicMock(spec=discord.File)
        mock_build_spin_gif.return_value = (new_file, "NewSkill")

        interaction = _make_interaction(role_names=["Member"], user_id=999)
        interaction.original_response = AsyncMock()
        interaction.followup.send = AsyncMock(
            return_value=MagicMock(spec=discord.Message)
        )
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "reroll_button", interaction, button)

        # Drive the Pay button on the ephemeral RerollPaymentView.
        followup_kwargs = interaction.followup.send.call_args.kwargs
        payment_view = followup_kwargs["view"]

        payment_button = MagicMock(spec=discord.ui.Button)
        pay_interaction = _make_interaction(user_id=999, role_names=["Member"])
        pay_interaction.original_response = AsyncMock()
        await _invoke_callback(
            payment_view, "confirm_button", pay_interaction, payment_button
        )

        self.assertTrue(self.view._lock_window_active)
        self.assertEqual(self.view._lock_window_user_id, 999)
        self.assertIn(self.view._lock_button, self.view.children)
        self.assertIn(self.view._dont_lock_button, self.view.children)

        if (
            self.view._lock_window_task is not None
            and not self.view._lock_window_task.done()
        ):
            self.view._lock_window_task.cancel()
            try:
                await self.view._lock_window_task
            except (asyncio.CancelledError, Exception):
                pass

    @patch("ironforgedbot.commands.admin.weekly_spin.build_payment_embed")
    @patch("ironforgedbot.commands.admin.weekly_spin.MemberService")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    @patch("ironforgedbot.commands.admin.weekly_spin._check_reroll_rate_limit")
    async def test_reroll_button_callback_signature_matches_discord_contract(
        self,
        mock_rate_limit,
        mock_db,
        mock_member_service_cls,
        mock_build_embed,
    ):
        """Discord calls ``item.callback(interaction)`` with a single argument;
        the wired adapter must accept that without TypeError.
        """
        mock_rate_limit.return_value = (True, 0)
        mock_member_service_cls.return_value = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_build_embed.return_value = MagicMock(spec=discord.Embed)

        interaction = _make_interaction(role_names=["Member"])
        interaction.followup.send = AsyncMock(
            return_value=MagicMock(spec=discord.Message)
        )

        # Single positional arg = Discord path. Must not raise TypeError.
        await self.view._reroll_button.callback(interaction)
        self.assertTrue(self.view.reroll_locked)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    async def test_lock_button_callbacks_signature_matches_discord_contract(
        self, mock_data, mock_find_emoji
    ):
        """Same single-arg contract applies to Lock and Don't Lock; the adapter
        must not raise TypeError even when the underlying handlers short-circuit
        on permission / state checks."""
        mock_data.SKILLS = [{"name": "Agility", "emoji_key": "agility"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        self.view._lock_window_active = True
        self.view._lock_window_user_id = 999
        self.view.current_winner = "Agility"

        rigger = _make_interaction(user_id=999, role_names=["Member"])
        # Don't Lock: free path, no DB needed.
        await self.view._dont_lock_button.callback(rigger)
        self.assertFalse(self.view._lock_window_active)

        # Re-open the window, then exercise Lock's insufficient-funds path.
        await self.view._open_lock_window(user_id=999)
        self.view._lock_window_task.cancel()
        try:
            await self.view._lock_window_task
        except (asyncio.CancelledError, Exception):
            pass

        with patch("ironforgedbot.commands.admin.weekly_spin.db") as mock_db, patch(
            "ironforgedbot.commands.admin.weekly_spin.create_ingot_service"
        ) as mock_create:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_db.get_session.return_value = mock_session
            fail = MagicMock()
            fail.status = False
            fail.new_total = 0
            mock_service = AsyncMock()
            mock_service.try_remove_ingots = AsyncMock(return_value=fail)
            mock_create.return_value = mock_service

            await self.view._lock_button.callback(rigger)
            self.assertTrue(
                self.view._lock_window_active,
                "insufficient funds must keep window open",
            )

    async def test_lock_window_rigger_can_lock_before_reveal(self):
        """The rigger's lock decision must not be blocked by the pending-reveal
        state; otherwise they get a confusing "Result is pending reveal"
        ephemeral right after their own reroll."""
        self.view._lock_window_active = True
        self.view._lock_window_user_id = 999
        self.view._lock_window_end_ts = int(time.time()) + 60
        # Reveal has NOT fired yet.
        self.view._reroll_unlocked = False
        self.view._apply_button_state()

        with patch(
            "ironforgedbot.commands.admin.weekly_spin.find_emoji",
            return_value="\U0001f3c3",
        ), patch(
            "ironforgedbot.commands.admin.weekly_spin.data",
            MagicMock(SKILLS=[{"name": "Agility", "emoji_key": "agility"}]),
        ), patch(
            "ironforgedbot.commands.admin.weekly_spin.create_ingot_service"
        ) as mock_create, patch(
            "ironforgedbot.commands.admin.weekly_spin.db"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_db.get_session.return_value = mock_session
            success = MagicMock()
            success.status = True
            success.new_total = 4000
            mock_service = AsyncMock()
            mock_service.try_remove_ingots = AsyncMock(return_value=success)
            mock_create.return_value = mock_service

            interaction = _make_interaction(user_id=999, role_names=["Member"])
            button = MagicMock(spec=discord.ui.Button)
            await _invoke_callback(self.view, "lock_button", interaction, button)

            mock_service.try_remove_ingots.assert_called_once()
            self.assertTrue(self.view._is_locked)

        # Cleanup the post-close lock-window task to let the test loop exit.
        if (
            self.view._lock_window_task is not None
            and not self.view._lock_window_task.done()
        ):
            self.view._lock_window_task.cancel()
            try:
                await self.view._lock_window_task
            except (asyncio.CancelledError, Exception):
                pass

    async def test_lock_window_rigger_can_dont_lock_before_reveal(self):
        """Same bypass for the Don't Lock button."""
        self.view._lock_window_active = True
        self.view._lock_window_user_id = 999
        self.view._lock_window_end_ts = int(time.time()) + 60
        self.view._reroll_unlocked = False
        self.view._apply_button_state()

        with patch(
            "ironforgedbot.commands.admin.weekly_spin.find_emoji",
            return_value="\U0001f3c3",
        ), patch(
            "ironforgedbot.commands.admin.weekly_spin.data",
            MagicMock(SKILLS=[{"name": "Agility", "emoji_key": "agility"}]),
        ):
            interaction = _make_interaction(user_id=999, role_names=["Member"])
            button = MagicMock(spec=discord.ui.Button)
            await _invoke_callback(self.view, "dont_lock_button", interaction, button)

        self.assertFalse(self.view._lock_window_active)
        self.assertFalse(self.view._is_locked)

        if (
            self.view._lock_window_task is not None
            and not self.view._lock_window_task.done()
        ):
            self.view._lock_window_task.cancel()
            try:
                await self.view._lock_window_task
            except (asyncio.CancelledError, Exception):
                pass

    async def test_close_lock_window_as_open_cancels_reveal_and_unlocks_reroll(self):
        """After Don't Lock (or timeout) the reroll button must be immediately
        enabled and the pending reveal task must be cancelled so it can't
        overwrite the post-decision state."""
        self.view._reroll_unlocked = False

        # Stand in a scheduled reveal task so we can verify cancellation.
        reveal_done = asyncio.Event()
        self.view._reveal_task = asyncio.create_task(asyncio.sleep(60))
        # Suppress the CancelledError log noise during test.
        try:
            with patch(
                "ironforgedbot.commands.admin.weekly_spin.find_emoji",
                return_value="\U0001f3c3",
            ), patch(
                "ironforgedbot.commands.admin.weekly_spin.data",
                MagicMock(SKILLS=[{"name": "Agility", "emoji_key": "agility"}]),
            ):
                self.view.current_winner = "Agility"
                await self.view._open_lock_window(user_id=999)
                self.view._lock_window_task.cancel()
                try:
                    await self.view._lock_window_task
                except (asyncio.CancelledError, Exception):
                    pass

                await self.view._close_lock_window_as_open(
                    message=self.target_message,
                    add_history_line=True,
                )

            self.assertTrue(self.view._reroll_unlocked)
            self.assertFalse(self.view._reroll_button.disabled)
            self.assertIsNone(self.view._reveal_task)
            # Cancel the stand-in reveal task; either already cancelled by
            # close-as-open or we cancel it here.
            if not reveal_done.is_set():
                reveal_done.set()
        finally:
            if self.view._reveal_task is not None and not self.view._reveal_task.done():
                self.view._reveal_task.cancel()

    async def test_close_lock_window_as_locked_cancels_reveal_task(self):
        """After Lock the reveal task must be cancelled so it doesn't
        overwrite the 🔒 header with a plain spoiler header."""
        self.view._reroll_unlocked = False
        self.view._reveal_task = asyncio.create_task(asyncio.sleep(60))

        try:
            with patch(
                "ironforgedbot.commands.admin.weekly_spin.find_emoji",
                return_value="\U0001f3c3",
            ), patch(
                "ironforgedbot.commands.admin.weekly_spin.data",
                MagicMock(SKILLS=[{"name": "Agility", "emoji_key": "agility"}]),
            ):
                self.view.current_winner = "Agility"
                await self.view._open_lock_window(user_id=999)
                self.view._lock_window_task.cancel()
                try:
                    await self.view._lock_window_task
                except (asyncio.CancelledError, Exception):
                    pass

                await self.view._close_lock_window_as_locked()

            self.assertTrue(self.view._is_locked)
            self.assertIsNone(self.view._reveal_task)
        finally:
            if self.view._reveal_task is not None and not self.view._reveal_task.done():
                self.view._reveal_task.cancel()

    async def test_reveal_task_is_noop_when_locked(self):
        """Belt-and-suspenders: even if the reveal task fires after the lock,
        it must not overwrite the locked content."""
        self.view._is_locked = True
        self.view.current_winner = "Agility"

        with patch(
            "ironforgedbot.commands.admin.weekly_spin.asyncio.sleep",
            new=AsyncMock(),
        ):
            await weekly_spin._reveal_winner_after_delay(
                message=self.target_message,
                view=self.view,
                kind="sotw",
                winner="Agility",
                history_lines=self.view.history_lines,
                reroll_close_ts=0,
            )

        self.target_message.edit.assert_not_called()


class TestRerollPaymentView(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.target_message = MagicMock(spec=discord.Message)
        self.target_message.edit = AsyncMock()
        self.target_message.clear_reactions = AsyncMock()
        self.target_message.add_reaction = AsyncMock()
        self.options = ["a", "b", "c"]
        self.parent_view = WeeklySpinView(
            options=self.options,
            kind="sotw",
            target_message=self.target_message,
        )
        self.parent_view.current_winner = "OldSkill"
        # Tests assume the parent view has already revealed; the reroll
        # flow can then be exercised in its "unlocked" steady state.
        self.parent_view._reroll_unlocked = True
        self.parent_view._apply_button_state()
        self.view = RerollPaymentView(parent_view=self.parent_view, user_id=999)

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_charges_and_edits_post(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_build_spin_gif,
        mock_data,
        mock_find_emoji,
    ):
        mock_data.SKILLS = [{"name": "NewSkill", "emoji_key": "newskill"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        success_response = MagicMock()
        success_response.status = True
        success_response.new_total = 5000
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success_response)
        mock_create_ingot_service.return_value = mock_service

        new_file = MagicMock(spec=discord.File)
        mock_build_spin_gif.return_value = (new_file, "NewSkill")

        interaction = _make_interaction(user_id=999)
        interaction.original_response = AsyncMock()
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "confirm_button", interaction, button)

        mock_service.try_remove_ingots.assert_called_once()
        call_args = mock_service.try_remove_ingots.call_args
        self.assertEqual(call_args.args[0], 999)
        self.assertEqual(call_args.args[1], -2500)
        self.assertIsNone(call_args.args[2])
        self.assertIn("Reroll weekly spin: SOTW", call_args.args[3])

        mock_build_spin_gif.assert_called_once_with(self.options)
        # The pending post-reveal edit carries the new GIF; the lock-window
        # edit fires after that with the countdown footer.
        pending_edits = [
            call
            for call in self.target_message.edit.call_args_list
            if "content" in call.kwargs and call.kwargs.get("attachments") == [new_file]
        ]
        self.assertEqual(len(pending_edits), 1)
        edit_kwargs = pending_edits[0].kwargs
        self.assertNotIn("NewSkill", edit_kwargs["content"])
        self.assertIn("# Next SOTW is...", edit_kwargs["content"])
        interaction.delete_original_response.assert_called_once()

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_appends_history_line(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_build_spin_gif,
        mock_data,
        mock_find_emoji,
    ):
        mock_data.SKILLS = [{"name": "NewSkill", "emoji_key": "newskill"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        success_response = MagicMock()
        success_response.status = True
        success_response.new_total = 5000
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success_response)
        mock_create_ingot_service.return_value = mock_service

        new_file = MagicMock(spec=discord.File)
        mock_build_spin_gif.return_value = (new_file, "NewSkill")

        interaction = _make_interaction(user_id=999)
        interaction.original_response = AsyncMock()
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "confirm_button", interaction, button)

        self.assertEqual(
            self.parent_view.history_lines,
            ["~~OldSkill~~ rerolled by <@999>"],
        )
        self.assertEqual(self.parent_view.current_winner, "NewSkill")

        # Pick the pending post-reveal edit (the one without attachments is
        # the lock-window footer; the one without the countdown is the
        # initial pending edit).
        pending_edits = [
            call
            for call in self.target_message.edit.call_args_list
            if "content" in call.kwargs and "attachments" in call.kwargs
        ]
        self.assertEqual(len(pending_edits), 1)
        edit_content = pending_edits[0].kwargs["content"]
        self.assertIn("~~OldSkill~~ rerolled by <@999>", edit_content)
        self.assertIn("# Next SOTW is...", edit_content)
        self.assertNotIn("NewSkill", edit_content)
        self.target_message.clear_reactions.assert_awaited_once()
        self.assertEqual(self.target_message.add_reaction.await_count, 2)
        reaction_calls = self.target_message.add_reaction.call_args_list
        self.assertEqual(reaction_calls[0].args[0], "\U0001f44d")
        self.assertEqual(reaction_calls[1].args[0], "\U0001f44e")

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_history_grows_across_multiple_rerolls(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_build_spin_gif,
        mock_data,
        mock_find_emoji,
    ):
        mock_data.SKILLS = [
            {"name": "NewSkill", "emoji_key": "newskill"},
            {"name": "ThirdSkill", "emoji_key": "thirdskill"},
        ]
        mock_find_emoji.return_value = "\U0001f3c3"

        success_response = MagicMock()
        success_response.status = True
        success_response.new_total = 5000
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success_response)
        mock_create_ingot_service.return_value = mock_service

        new_file = MagicMock(spec=discord.File)
        mock_build_spin_gif.side_effect = [
            (new_file, "NewSkill"),
            (new_file, "ThirdSkill"),
        ]

        interaction1 = _make_interaction(user_id=111)
        interaction1.original_response = AsyncMock()
        interaction2 = _make_interaction(user_id=222)
        interaction2.original_response = AsyncMock()
        button = MagicMock(spec=discord.ui.Button)

        view1 = RerollPaymentView(parent_view=self.parent_view, user_id=111)
        view2 = RerollPaymentView(parent_view=self.parent_view, user_id=222)
        await _invoke_callback(view1, "confirm_button", interaction1, button)
        await _invoke_callback(view2, "confirm_button", interaction2, button)

        self.assertEqual(
            self.parent_view.history_lines,
            [
                "~~OldSkill~~ rerolled by <@111>",
                "~~NewSkill~~ rerolled by <@222>",
            ],
        )
        self.assertEqual(self.parent_view.current_winner, "ThirdSkill")

    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_releases_lock_and_re_enables_on_success(
        self, mock_db, mock_create_ingot_service
    ):
        with patch(
            "ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file",
            return_value=(MagicMock(spec=discord.File), "NewSkill"),
        ):
            mock_data_patch = patch(
                "ironforgedbot.commands.admin.weekly_spin.data",
                SKILLS=[{"name": "NewSkill", "emoji_key": "newskill"}],
            )
            mock_data_patch.start()
            self.parent_view.reroll_locked = True
            child = MagicMock(spec=discord.ui.Item)
            child.disabled = True
            self.parent_view._children = [child]

            success_response = MagicMock()
            success_response.status = True
            success_response.new_total = 5000
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_db.get_session.return_value = mock_session
            mock_service = AsyncMock()
            mock_service.try_remove_ingots = AsyncMock(return_value=success_response)
            mock_create_ingot_service.return_value = mock_service

            interaction = _make_interaction(user_id=999)
            interaction.original_response = AsyncMock()
            button = MagicMock(spec=discord.ui.Button)
            await _invoke_callback(self.view, "confirm_button", interaction, button)

            self.assertFalse(self.parent_view.reroll_locked)
            self.assertFalse(self.parent_view._reroll_unlocked)
            self.assertTrue(child.disabled)
            self.target_message.edit.call_args_list[-1]
            self.target_message.clear_reactions.assert_awaited_once()
            self.assertEqual(self.target_message.add_reaction.await_count, 2)
            mock_data_patch.stop()

    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_clears_and_readds_reactions_on_success(
        self, mock_db, mock_create_ingot_service
    ):
        with patch(
            "ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file",
            return_value=(MagicMock(spec=discord.File), "NewSkill"),
        ):
            mock_data_patch = patch(
                "ironforgedbot.commands.admin.weekly_spin.data",
                SKILLS=[{"name": "NewSkill", "emoji_key": "newskill"}],
            )
            mock_data_patch.start()
            success_response = MagicMock()
            success_response.status = True
            success_response.new_total = 5000
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_db.get_session.return_value = mock_session
            mock_service = AsyncMock()
            mock_service.try_remove_ingots = AsyncMock(return_value=success_response)
            mock_create_ingot_service.return_value = mock_service

            interaction = _make_interaction(user_id=999)
            interaction.original_response = AsyncMock()
            button = MagicMock(spec=discord.ui.Button)
            await _invoke_callback(self.view, "confirm_button", interaction, button)

            self.target_message.clear_reactions.assert_awaited_once()
            self.assertEqual(self.target_message.add_reaction.await_count, 2)
            reaction_calls = self.target_message.add_reaction.call_args_list
            self.assertEqual(reaction_calls[0].args[0], "\U0001f44d")
            self.assertEqual(reaction_calls[1].args[0], "\U0001f44e")
            mock_data_patch.stop()

    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_continues_when_clear_reactions_forbidden(
        self, mock_db, mock_create_ingot_service
    ):
        with patch(
            "ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file",
            return_value=(MagicMock(spec=discord.File), "NewSkill"),
        ):
            mock_data_patch = patch(
                "ironforgedbot.commands.admin.weekly_spin.data",
                SKILLS=[{"name": "NewSkill", "emoji_key": "newskill"}],
            )
            mock_data_patch.start()
            self.target_message.clear_reactions.side_effect = discord.Forbidden(
                MagicMock(), "no perms"
            )
            success_response = MagicMock()
            success_response.status = True
            success_response.new_total = 5000
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_db.get_session.return_value = mock_session
            mock_service = AsyncMock()
            mock_service.try_remove_ingots = AsyncMock(return_value=success_response)
            mock_create_ingot_service.return_value = mock_service

            interaction = _make_interaction(user_id=999)
            interaction.original_response = AsyncMock()
            button = MagicMock(spec=discord.ui.Button)
            await _invoke_callback(self.view, "confirm_button", interaction, button)

            # Reroll still completes; reactions just weren't reset.
            self.target_message.edit.assert_called()
            interaction.delete_original_response.assert_called_once()
            self.target_message.add_reaction.assert_not_called()
            mock_data_patch.stop()

    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_insufficient_funds_releases_lock(
        self, mock_db, mock_create_ingot_service
    ):
        self.parent_view.reroll_locked = True
        self.parent_view._reroll_button.disabled = True

        fail_response = MagicMock()
        fail_response.status = False
        fail_response.new_total = 100
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=fail_response)
        mock_create_ingot_service.return_value = mock_service

        interaction = _make_interaction(user_id=999)
        interaction.original_response = AsyncMock()
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "confirm_button", interaction, button)

        self.assertFalse(self.parent_view.reroll_locked)
        self.assertFalse(self.parent_view._reroll_button.disabled)
        for call in self.target_message.edit.call_args_list:
            self.assertNotIn("content", call.kwargs)
            self.assertNotIn("attachments", call.kwargs)
        interaction.delete_original_response.assert_called_once()

    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_gif_failure_releases_lock(
        self, mock_db, mock_create_ingot_service
    ):
        self.parent_view.reroll_locked = True
        self.parent_view._reroll_button.disabled = True

        success_response = MagicMock()
        success_response.status = True
        success_response.new_total = 5000
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success_response)
        mock_create_ingot_service.return_value = mock_service

        with patch(
            "ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file",
            side_effect=RuntimeError("gif failed"),
        ):
            interaction = _make_interaction(user_id=999)
            interaction.original_response = AsyncMock()
            button = MagicMock(spec=discord.ui.Button)
            await _invoke_callback(self.view, "confirm_button", interaction, button)

            self.assertFalse(self.parent_view.reroll_locked)
            self.assertFalse(self.parent_view._reroll_button.disabled)
            interaction.delete_original_response.assert_called()

    async def test_confirm_target_message_none_rejected(self):
        parent = WeeklySpinView(options=self.options, kind="sotw", target_message=None)
        parent.current_winner = "OldSkill"
        view = RerollPaymentView(parent_view=parent, user_id=999)

        interaction = _make_interaction(user_id=999)
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(view, "confirm_button", interaction, button)

        interaction.response.send_message.assert_called_once()
        self.assertIn(
            "no longer exists",
            interaction.response.send_message.call_args.args[0],
        )

    async def test_cancel_releases_lock_and_deletes_payment_message(self):
        self.parent_view.reroll_locked = True
        self.parent_view._reroll_button.disabled = True

        interaction = _make_interaction(user_id=999)
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "cancel_button", interaction, button)

        self.assertFalse(self.parent_view.reroll_locked)
        self.assertFalse(self.parent_view._reroll_button.disabled)
        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.delete_original_response.assert_called_once()

    async def test_cancel_deletes_ephemeral_when_message_never_set(self):
        self.view.message = None
        interaction = _make_interaction(user_id=999)
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "cancel_button", interaction, button)

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.delete_original_response.assert_called_once()
        self.assertFalse(self.parent_view.reroll_locked)

    async def test_on_timeout_releases_lock_and_re_enables(self):
        self.parent_view.reroll_locked = True
        self.parent_view._reroll_button.disabled = True
        self.view.message = AsyncMock()
        self.view.message.delete = AsyncMock()

        await self.view.on_timeout()

        self.assertFalse(self.parent_view.reroll_locked)
        # RerollPaymentView.on_timeout just releases the parent lock — the
        # Re-roll button stays in the view and gets re-enabled.
        self.assertFalse(self.parent_view._reroll_button.disabled)
        self.view.message.delete.assert_called_once()

    async def test_confirm_rejects_other_user(self):
        interaction = _make_interaction(user_id=42)
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "confirm_button", interaction, button)

        interaction.response.send_message.assert_called_once()
        self.assertIn(
            "not for you",
            interaction.response.send_message.call_args.args[0],
        )
        self.target_message.edit.assert_not_called()

    async def test_cancel_rejects_other_user(self):
        interaction = _make_interaction(user_id=42)
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "cancel_button", interaction, button)

        interaction.response.send_message.assert_called_once()
        self.assertIn(
            "not for you",
            interaction.response.send_message.call_args.args[0],
        )
        interaction.delete_original_response.assert_not_called()

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_deletes_ephemeral_before_gif_build(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_build_spin_gif,
        mock_data,
        mock_find_emoji,
    ):
        """After a successful debit the ephemeral payment embed must be
        removed before the slow GIF build kicks off — the user has paid, so
        the prompt no longer needs to be on screen during the heavy work."""
        mock_data.SKILLS = [{"name": "NewSkill", "emoji_key": "newskill"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        success_response = MagicMock()
        success_response.status = True
        success_response.new_total = 5000
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session
        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success_response)
        mock_create_ingot_service.return_value = mock_service

        delete_seen_at_gif_time = {"value": False}

        async def fake_delete():
            delete_seen_at_gif_time["delete_called"] = True

        async def fake_gif(_options):
            # Snapshot whether delete_original_response already fired by the
            # time the GIF build starts.
            delete_seen_at_gif_time["value"] = delete_seen_at_gif_time.get(
                "delete_called", False
            )
            return MagicMock(spec=discord.File), "NewSkill"

        interaction = _make_interaction(user_id=999)
        interaction.original_response = AsyncMock()
        interaction.delete_original_response = AsyncMock(side_effect=fake_delete)
        mock_build_spin_gif.side_effect = fake_gif

        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "confirm_button", interaction, button)

        self.assertTrue(
            delete_seen_at_gif_time["value"],
            "delete_original_response must fire before build_spin_gif_file",
        )
        interaction.delete_original_response.assert_called_once()
        mock_build_spin_gif.assert_called_once()


class TestRerollButtonDoubleClick(unittest.IsolatedAsyncioTestCase):
    """Concurrency guard on the Re-roll button (WeeklySpinView).

    Discord invokes ``interaction_check`` before every button callback. The
    lock must be set synchronously inside the callback so that, by the time
    the first await yields, a second click's interaction_check sees the
    locked flag and bails out before invoking the callback a second time.
    """

    def setUp(self):
        self.target_message = MagicMock(spec=discord.Message)
        self.target_message.edit = AsyncMock()
        self.view = WeeklySpinView(
            options=["a", "b", "c"], kind="sotw", target_message=self.target_message
        )
        self.view._reroll_unlocked = True
        self.view._apply_button_state()

    async def test_reroll_locks_synchronously_before_first_await(self):
        """A second click that arrives after the first yields must be denied
        by interaction_check, because the first callback flipped the lock
        before any await."""
        interaction = _make_interaction(role_names=["Member"])

        real_defer = interaction.response.defer

        async def defer_then_check(*args, **kwargs):
            await real_defer(*args, **kwargs)

        interaction.response.defer = defer_then_check

        self.view._reroll_button.disabled = False

        callback = type(self.view).reroll_button

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        mock_member_service_cls = MagicMock()
        mock_member_service = AsyncMock()
        mock_member_service.get_member_by_discord_id = AsyncMock(
            return_value=MagicMock(ingots=9999)
        )
        mock_member_service_cls.return_value = mock_member_service

        with patch(
            "ironforgedbot.commands.admin.weekly_spin.build_payment_embed"
        ) as mock_embed, patch(
            "ironforgedbot.commands.admin.weekly_spin.MemberService",
            mock_member_service_cls,
        ), patch(
            "ironforgedbot.commands.admin.weekly_spin.db"
        ) as mock_db, patch(
            "ironforgedbot.commands.admin.weekly_spin._check_reroll_rate_limit",
            return_value=(True, 0),
        ):
            mock_db.get_session.return_value = mock_session
            mock_embed.return_value = MagicMock(spec=discord.Embed)
            sent_message = MagicMock(spec=discord.Message)
            interaction.followup.send = AsyncMock(return_value=sent_message)
            button = MagicMock(spec=discord.ui.Button)
            await callback(self.view, interaction, button)

        # By the time the first callback's defer yielded, a second click's
        # interaction_check must have seen the locked flag.
        self.assertTrue(self.view.reroll_locked)
        self.assertTrue(self.view._reroll_button.disabled)

        second = _make_interaction(role_names=["Member"])
        result = await self.view.interaction_check(second)
        self.assertFalse(result)
        second.response.send_message.assert_called_once()
        self.assertIn("in progress", second.response.send_message.call_args.args[0])


class TestRerollPaymentDoubleCharge(unittest.IsolatedAsyncioTestCase):
    """Concurrency guards on the Pay button.

    These tests stand apart from TestRerollPaymentView because they need a
    freshly constructed view per scenario to exercise the completed-flag
    idempotency contract.
    """

    def _make_parent(self):
        target_message = MagicMock(spec=discord.Message)
        target_message.edit = AsyncMock()
        target_message.clear_reactions = AsyncMock()
        target_message.add_reaction = AsyncMock()
        parent = WeeklySpinView(
            options=["a", "b", "c"], kind="sotw", target_message=target_message
        )
        parent._reroll_unlocked = True
        parent._apply_button_state()
        parent.current_winner = "OldSkill"
        return parent

    async def test_confirm_pay_second_click_is_noop(self):
        """If the completed flag is already set, a subsequent Pay click must
        not interact with the DB, the parent view, or Discord."""
        parent = self._make_parent()
        view = RerollPaymentView(parent_view=parent, user_id=999)
        view.completed = True

        interaction = _make_interaction(user_id=999)
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(view, "confirm_button", interaction, button)

        interaction.response.defer.assert_not_called()
        interaction.followup.send.assert_not_called()
        interaction.delete_original_response.assert_not_called()
        parent.target_message.edit.assert_not_called()

    @patch("ironforgedbot.commands.admin.weekly_spin.find_emoji")
    @patch("ironforgedbot.commands.admin.weekly_spin.data")
    @patch("ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file")
    @patch("ironforgedbot.commands.admin.weekly_spin.create_ingot_service")
    @patch("ironforgedbot.commands.admin.weekly_spin.db")
    async def test_confirm_double_click_only_charges_once(
        self,
        mock_db,
        mock_create_ingot_service,
        mock_build_spin_gif,
        mock_data,
        mock_find_emoji,
    ):
        """Two Pay clicks within the same event loop tick must result in
        exactly one ingot deduction and one GIF rebuild."""
        mock_data.SKILLS = [{"name": "NewSkill", "emoji_key": "newskill"}]
        mock_find_emoji.return_value = "\U0001f3c3"

        success_response = MagicMock()
        success_response.status = True
        success_response.new_total = 5000

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_db.get_session.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.try_remove_ingots = AsyncMock(return_value=success_response)
        mock_create_ingot_service.return_value = mock_service

        new_file = MagicMock(spec=discord.File)
        mock_build_spin_gif.return_value = (new_file, "NewSkill")

        parent = self._make_parent()
        view = RerollPaymentView(parent_view=parent, user_id=999)
        button = MagicMock(spec=discord.ui.Button)

        interaction1 = _make_interaction(user_id=999)
        interaction2 = _make_interaction(user_id=999)

        await asyncio.gather(
            _invoke_callback(view, "confirm_button", interaction1, button),
            _invoke_callback(view, "confirm_button", interaction2, button),
        )

        mock_service.try_remove_ingots.assert_called_once()
        mock_build_spin_gif.assert_called_once()
