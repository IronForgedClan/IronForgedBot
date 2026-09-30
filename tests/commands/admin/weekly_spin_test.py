import asyncio
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

        child = MagicMock(spec=discord.ui.Item)
        child.disabled = False
        self.view._children = [child]

        interaction = _make_interaction(role_names=["Member"])
        button = MagicMock(spec=discord.ui.Button)
        await _invoke_callback(self.view, "reroll_button", interaction, button)

        self.assertTrue(self.view.reroll_locked)
        self.assertTrue(child.disabled)
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
        child = MagicMock(spec=discord.ui.Item)
        child.disabled = False
        self.view._children = [child]

        await self.view.on_timeout()

        self.assertTrue(child.disabled)
        self.assertTrue(self.view._timed_out)
        self.target_message.edit.assert_called_once()
        edit_kwargs = self.target_message.edit.call_args.kwargs
        self.assertIn("content", edit_kwargs)
        self.assertNotIn("-# Re-roll window", edit_kwargs["content"])
        self.assertIn("# Next SOTW is ||\U0001f40d Zulrah||", edit_kwargs["content"])

    async def test_on_timeout_without_current_winner_skips_content_edit(self):
        self.view.target_message = self.target_message
        child = MagicMock(spec=discord.ui.Item)
        child.disabled = False
        self.view._children = [child]

        await self.view.on_timeout()

        self.assertTrue(child.disabled)
        self.target_message.edit.assert_called_once()
        self.assertNotIn("content", self.target_message.edit.call_args.kwargs)

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
        child = MagicMock(spec=discord.ui.Item)
        child.disabled = True
        self.view._children = [child]
        self.view._reroll_unlocked = True
        self.view.reroll_locked = False
        self.view._apply_button_state()
        self.assertFalse(child.disabled)

    def test_apply_button_state_disables_while_concurrent_locked(self):
        child = MagicMock(spec=discord.ui.Item)
        child.disabled = False
        self.view._children = [child]
        self.view._reroll_unlocked = True
        self.view.reroll_locked = True
        self.view._apply_button_state()
        self.assertTrue(child.disabled)


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
        edit_calls = [
            call
            for call in self.target_message.edit.call_args_list
            if "content" in call.kwargs
        ]
        self.assertEqual(len(edit_calls), 1)
        edit_kwargs = edit_calls[0].kwargs
        self.assertNotIn("NewSkill", edit_kwargs["content"])
        self.assertIn("# Next SOTW is...", edit_kwargs["content"])
        self.assertEqual(edit_kwargs["attachments"], [new_file])
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

        edit_calls = [
            call
            for call in self.target_message.edit.call_args_list
            if "content" in call.kwargs
        ]
        self.assertEqual(len(edit_calls), 1)
        edit_content = edit_calls[0].kwargs["content"]
        self.assertIn("~~OldSkill~~ rerolled by <@999>", edit_content)
        self.assertIn("# Next SOTW is...", edit_content)
        self.assertNotIn("NewSkill", edit_content)
        self.assertIn("-# Re-roll window closes <t:", edit_content)
        self.assertIn(":R>.", edit_content)
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
        child = MagicMock(spec=discord.ui.Item)
        child.disabled = True
        self.parent_view._children = [child]

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
        self.assertFalse(child.disabled)
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

        with patch(
            "ironforgedbot.commands.admin.weekly_spin.build_spin_gif_file",
            side_effect=RuntimeError("gif failed"),
        ):
            interaction = _make_interaction(user_id=999)
            interaction.original_response = AsyncMock()
            button = MagicMock(spec=discord.ui.Button)
            await _invoke_callback(self.view, "confirm_button", interaction, button)

            self.assertFalse(self.parent_view.reroll_locked)
            self.assertFalse(child.disabled)
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
        child = MagicMock(spec=discord.ui.Item)
        child.disabled = True
        self.parent_view._children = [child]

        interaction = _make_interaction(user_id=999)
        button = MagicMock(spec=discord.ui.Button)

        await _invoke_callback(self.view, "cancel_button", interaction, button)

        self.assertFalse(self.parent_view.reroll_locked)
        self.assertFalse(child.disabled)
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
        child = MagicMock(spec=discord.ui.Item)
        child.disabled = True
        self.parent_view._children = [child]
        self.view.message = AsyncMock()
        self.view.message.delete = AsyncMock()

        await self.view.on_timeout()

        self.assertFalse(self.parent_view.reroll_locked)
        self.assertFalse(child.disabled)
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

        child = MagicMock(spec=discord.ui.Item)
        child.disabled = False
        self.view._children = [child]

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
        self.assertTrue(child.disabled)

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
