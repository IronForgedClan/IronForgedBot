import unittest
from unittest.mock import Mock, patch

import discord

from ironforgedbot.common.roles import ROLE
from tests.helpers import (
    VALID_CONFIG,
    create_mock_discord_interaction,
    create_test_member,
    mock_require_role,
)

with patch("ironforgedbot.decorators.require_role.require_role", mock_require_role):
    with patch(
        "ironforgedbot.common.logging_utils.log_command_execution",
        lambda *a, **kw: lambda f: f,
    ):
        from ironforgedbot.commands.help.cmd_help import (
            cmd_help,
            _get_ingot_cost,
            _build_ascii_table,
            _build_commands_description,
            _build_activities_description,
            _DESC_WRAP_WIDTH,
        )


def _make_command(name: str, description: str, ingot_cost: int | None = None) -> Mock:
    cmd = Mock(spec=discord.app_commands.Command)
    cmd.name = name
    cmd.description = description

    callback = Mock()
    callback.ingot_cost = ingot_cost
    callback.__wrapped__ = None
    cmd.callback = callback

    return cmd


@patch.dict("os.environ", VALID_CONFIG)
class TestCmdHelp(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        test_member = create_test_member("TestPlayer", [ROLE.MEMBER], "TestPlayer")
        self.mock_interaction = create_mock_discord_interaction(user=test_member)
        self.mock_tree = Mock()
        self.mock_interaction.client = Mock()
        self.mock_interaction.client.tree = self.mock_tree

    def _setup_commands(self, commands: list[Mock]):
        self.mock_tree.get_commands.return_value = commands

    async def test_cmd_help_sends_embed(self):
        self._setup_commands([])

        await cmd_help(self.mock_interaction)

        self.mock_interaction.followup.send.assert_called_once()
        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        self.assertIsInstance(embed, discord.Embed)

    async def test_cmd_help_embed_title(self):
        self._setup_commands([])

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        self.assertIn("Iron Forged Commands", embed.title)

    async def test_cmd_help_stats_lookup_section_present(self):
        self._setup_commands(
            [
                _make_command("score", "View the player's score."),
                _make_command("whois", "View player's rsn history."),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        field_names = [f.name for f in embed.fields]
        self.assertTrue(any("Core Commands" in n for n in field_names))

    async def test_cmd_help_games_fun_section_present(self):
        self._setup_commands(
            [
                _make_command("raffle", "Play the raffle."),
                _make_command(
                    "reset_rng", "💰 Attempt to reset your RNG.", ingot_cost=999
                ),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        field_names = [f.name for f in embed.fields]
        self.assertTrue(any("Activities" in n for n in field_names))

    async def test_cmd_help_leadership_commands_excluded(self):
        self._setup_commands(
            [
                _make_command("score", "View the player's score."),
                _make_command("admin", "🔒 Admin actions."),
                _make_command("roster", "🔒 Creates an event roster."),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        all_values = " ".join(f.value for f in embed.fields)
        self.assertNotIn("/admin", all_values)
        self.assertNotIn("/roster", all_values)
        self.assertNotIn("🔒", all_values)

    async def test_cmd_help_excludes_itself(self):
        self._setup_commands(
            [
                _make_command("help", "View all available bot commands."),
                _make_command("score", "View the player's score."),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        all_values = " ".join(f.value for f in embed.fields)
        self.assertNotIn("/help", all_values)

    async def test_cmd_help_ingot_cost_shown_in_games_section(self):
        self._setup_commands(
            [
                _make_command(
                    "reset_rng", "💰 Attempt to reset your RNG.", ingot_cost=999
                ),
                _make_command(
                    "eight_ball", "💰 Ask the Magic 8-Ball a question.", ingot_cost=1999
                ),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        games_value = next(f.value for f in embed.fields if "Activities" in f.name)
        self.assertIn("999", games_value)
        self.assertIn("1,999", games_value)

    async def test_cmd_help_no_ingot_cost_for_free_commands(self):
        self._setup_commands(
            [
                _make_command("score", "View the player's score."),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        stats_value = next(f.value for f in embed.fields if "Core Commands" in f.name)
        self.assertNotIn("ingots", stats_value.split("```")[1])

    async def test_cmd_help_stats_section_contains_channel_links(self):
        self._setup_commands(
            [
                _make_command("score", "View the player's score."),
            ]
        )

        with patch("ironforgedbot.commands.help.cmd_help.CONFIG") as mock_config, patch(
            "ironforgedbot.commands.help.cmd_help.STATE"
        ) as mock_state:
            mock_config.RULES_CHANNEL_ID = 111
            mock_config.INGOT_SHOP_CHANNEL_ID = 222
            mock_config.RAFFLE_CHANNEL_ID = 333
            mock_config.TRICK_OR_TREAT_CHANNEL_ID = None
            mock_config.BOT_COMMANDS_CHANNEL_ID = 0
            mock_config.CREATE_TICKET_CHANNEL_ID = 0
            mock_config.BOT_CHANGELOG_CHANNEL_ID = 0
            mock_config.BOT_VERSION = "0.0.0"
            mock_state.state = {"raffle_on": False}

            await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        stats_value = next(f.value for f in embed.fields if "Core Commands" in f.name)
        self.assertIn("<#111>", stats_value)
        self.assertIn("<#222>", stats_value)

    async def test_cmd_help_games_section_contains_raffle_channel_link(self):
        self._setup_commands(
            [
                _make_command("raffle", "Play the raffle."),
            ]
        )

        with patch("ironforgedbot.commands.help.cmd_help.CONFIG") as mock_config, patch(
            "ironforgedbot.commands.help.cmd_help.STATE"
        ) as mock_state:
            mock_config.RULES_CHANNEL_ID = 111
            mock_config.INGOT_SHOP_CHANNEL_ID = 222
            mock_config.RAFFLE_CHANNEL_ID = 333
            mock_config.TRICK_OR_TREAT_CHANNEL_ID = None
            mock_config.BOT_COMMANDS_CHANNEL_ID = 0
            mock_config.CREATE_TICKET_CHANNEL_ID = 0
            mock_config.BOT_CHANGELOG_CHANNEL_ID = 0
            mock_config.BOT_VERSION = "0.0.0"
            mock_state.state = {"raffle_on": True}

            await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        games_value = next(f.value for f in embed.fields if "Activities" in f.name)
        self.assertIn("<#333>", games_value)

    async def test_cmd_help_trick_or_treat_channel_shown_when_present(self):
        self._setup_commands(
            [
                _make_command("trick_or_treat", "💰 Feeling lucky, punk?"),
            ]
        )

        with patch("ironforgedbot.commands.help.cmd_help.CONFIG") as mock_config, patch(
            "ironforgedbot.commands.help.cmd_help.STATE"
        ) as mock_state:
            mock_config.RULES_CHANNEL_ID = 1
            mock_config.INGOT_SHOP_CHANNEL_ID = 2
            mock_config.RAFFLE_CHANNEL_ID = 3
            mock_config.TRICK_OR_TREAT_CHANNEL_ID = 444
            mock_config.BOT_COMMANDS_CHANNEL_ID = 0
            mock_config.CREATE_TICKET_CHANNEL_ID = 0
            mock_config.BOT_CHANGELOG_CHANNEL_ID = 0
            mock_config.BOT_VERSION = "0.0.0"
            mock_state.state = {"raffle_on": False}

            await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        games_value = next(f.value for f in embed.fields if "Activities" in f.name)
        self.assertIn("<#444>", games_value)

    async def test_cmd_help_trick_or_treat_channel_hidden_when_not_configured(self):
        self._setup_commands(
            [
                _make_command("trick_or_treat", "💰 Feeling lucky, punk?"),
            ]
        )

        with patch("ironforgedbot.commands.help.cmd_help.CONFIG") as mock_config, patch(
            "ironforgedbot.commands.help.cmd_help.STATE"
        ) as mock_state:
            mock_config.RULES_CHANNEL_ID = 1
            mock_config.INGOT_SHOP_CHANNEL_ID = 2
            mock_config.RAFFLE_CHANNEL_ID = 3
            mock_config.TRICK_OR_TREAT_CHANNEL_ID = None
            mock_config.BOT_COMMANDS_CHANNEL_ID = 0
            mock_config.CREATE_TICKET_CHANNEL_ID = 0
            mock_config.BOT_CHANGELOG_CHANNEL_ID = 0
            mock_config.BOT_VERSION = "0.0.0"
            mock_state.state = {"raffle_on": False}

            await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        games_value = next(f.value for f in embed.fields if "Activities" in f.name)
        self.assertNotIn("<#444>", games_value)

    async def test_cmd_help_unknown_commands_go_to_other_section(self):
        self._setup_commands(
            [
                _make_command("brand_new_command", "Does something new."),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        field_names = [f.name for f in embed.fields]
        self.assertTrue(any("Miscellaneous" in n for n in field_names))

    async def test_cmd_help_empty_section_not_shown(self):
        self._setup_commands(
            [
                _make_command("score", "View the player's score."),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        field_names = [f.name for f in embed.fields]
        self.assertFalse(any("Activities" in n for n in field_names))
        self.assertFalse(any("Miscellaneous" in n for n in field_names))

    async def test_cmd_help_commands_preserve_registration_order(self):
        self._setup_commands(
            [
                _make_command("check", "Check your account."),
                _make_command("ingots", "View your ingot balance."),
                _make_command("score", "View the player's score."),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        stats_value = next(f.value for f in embed.fields if "Core Commands" in f.name)
        table_part = stats_value.split("```")[1]
        check_pos = table_part.index("check")
        ingots_pos = table_part.index("ingots")
        score_pos = table_part.index("score")
        self.assertLess(check_pos, ingots_pos)
        self.assertLess(ingots_pos, score_pos)

    async def test_cmd_help_emoji_prefix_stripped_from_description(self):
        self._setup_commands(
            [
                _make_command(
                    "reset_rng", "💰 Attempt to reset your RNG.", ingot_cost=999
                ),
            ]
        )

        await cmd_help(self.mock_interaction)

        embed = self.mock_interaction.followup.send.call_args[1]["embed"]
        games_value = next(f.value for f in embed.fields if "Activities" in f.name)
        self.assertIn("Attempt to reset your RNG.", games_value)
        self.assertNotIn("💰 Attempt", games_value)


@patch.dict("os.environ", VALID_CONFIG)
class TestGetIngotCost(unittest.TestCase):
    def test_returns_cost_when_stamped_on_callback(self):
        cmd = _make_command(
            "reset_rng", "💰 Attempt to reset your RNG.", ingot_cost=999
        )
        self.assertEqual(_get_ingot_cost(cmd), 999)

    def test_returns_none_when_no_cost(self):
        cmd = _make_command("score", "View the player's score.")
        self.assertIsNone(_get_ingot_cost(cmd))

    def test_walks_wrapped_chain(self):
        cmd = Mock(spec=discord.app_commands.Command)
        cmd.name = "spin"
        cmd.description = "💰 Spin a wheel."

        inner = Mock()
        inner.ingot_cost = 3499
        inner.__wrapped__ = None

        outer = Mock()
        del outer.ingot_cost
        outer.__wrapped__ = inner

        cmd.callback = outer
        self.assertEqual(_get_ingot_cost(cmd), 3499)


@patch.dict("os.environ", VALID_CONFIG)
class TestBuildAsciiTable(unittest.TestCase):
    def test_wraps_output_in_code_block(self):
        cmds = [_make_command("score", "View the player's score.")]
        result = _build_ascii_table(cmds)
        self.assertTrue(result.startswith("```"))
        self.assertTrue(result.endswith("```"))

    def test_has_header_separator_row(self):
        cmds = [_make_command("score", "View the player's score.")]
        result = _build_ascii_table(cmds)
        table = result.strip("`")
        separator_lines = [
            l for l in table.splitlines() if set(l.strip()) <= set("- ") and l.strip()
        ]
        self.assertTrue(len(separator_lines) > 0)

    def test_headers_present(self):
        cmds = [_make_command("score", "View the player's score.")]
        result = _build_ascii_table(cmds)
        self.assertIn("Command", result)
        self.assertIn("Description", result)

    def test_cost_header_present_when_costs_exist(self):
        cmds = [
            _make_command("reset_rng", "💰 Attempt to reset your RNG.", ingot_cost=999)
        ]
        result = _build_ascii_table(cmds)
        self.assertIn("ingots", result)

    def test_no_cost_header_when_all_commands_are_free(self):
        cmds = [_make_command("score", "View the player's score.")]
        result = _build_ascii_table(cmds)
        self.assertNotIn("ingots", result)

    def test_includes_command_name_and_description(self):
        cmds = [_make_command("score", "View the player's score.")]
        result = _build_ascii_table(cmds)
        self.assertIn("score", result)
        self.assertIn("View the player's score.", result)

    def test_long_description_is_wrapped(self):
        long_desc = "A" * (_DESC_WRAP_WIDTH + 10) + " " + "B" * 5
        cmds = [_make_command("score", long_desc)]
        result = _build_ascii_table(cmds)
        self.assertGreaterEqual(result.count("\n"), 3)

    def test_cost_column_present_when_any_command_has_cost(self):
        cmds = [
            _make_command("raffle", "Play the raffle."),
            _make_command("reset_rng", "💰 Attempt to reset your RNG.", ingot_cost=999),
        ]
        result = _build_ascii_table(cmds)
        self.assertIn("ingots", result)

    def test_free_command_has_blank_cost_cell_when_others_have_cost(self):
        cmds = [
            _make_command("raffle", "Play the raffle."),
            _make_command("reset_rng", "💰 Attempt to reset your RNG.", ingot_cost=999),
        ]
        result = _build_ascii_table(cmds)
        table = result.strip("`")
        raffle_line = next(l for l in table.splitlines() if "raffle " in l)
        self.assertNotIn("ingots", raffle_line)

    def test_no_cost_column_when_all_commands_are_free(self):
        cmds = [
            _make_command("score", "View the player's score."),
            _make_command("breakdown", "View the player's score breakdown."),
        ]
        result = _build_ascii_table(cmds)
        self.assertNotIn("ingots", result)

    def test_large_cost_formatted_with_comma(self):
        cmds = [_make_command("eight_ball", "💰 Ask a question.", ingot_cost=1999)]
        result = _build_ascii_table(cmds)
        self.assertIn("1,999", result)

    def test_strips_emoji_prefix_from_description(self):
        cmds = [
            _make_command("reset_rng", "💰 Attempt to reset your RNG.", ingot_cost=999)
        ]
        result = _build_ascii_table(cmds)
        self.assertNotIn("💰 Attempt", result)
        self.assertIn("Attempt to reset your RNG.", result)

    def test_columns_are_aligned(self):
        cmds = [
            _make_command("score", "Alpha description."),
            _make_command("breakdown", "Beta description."),
        ]
        result = _build_ascii_table(cmds)
        table = result.strip("`")
        lines = table.splitlines()
        score_line = next(l for l in lines if "score " in l)
        breakdown_line = next(l for l in lines if "breakdown" in l)
        self.assertEqual(score_line.index("Alpha"), breakdown_line.index("Beta"))


@patch.dict("os.environ", VALID_CONFIG)
class TestBuildCommandsDescription(unittest.TestCase):
    def test_contains_rules_and_shop_mentions(self):
        with patch("ironforgedbot.commands.help.cmd_help.CONFIG") as mock_config:
            mock_config.RULES_CHANNEL_ID = 111
            mock_config.INGOT_SHOP_CHANNEL_ID = 222
            result = _build_commands_description()
        self.assertIn("<#111>", result)
        self.assertIn("<#222>", result)


@patch.dict("os.environ", VALID_CONFIG)
class TestBuildActivitiesDescription(unittest.TestCase):
    def test_contains_raffle_mention(self):
        with patch("ironforgedbot.commands.help.cmd_help.CONFIG") as mock_config, patch(
            "ironforgedbot.commands.help.cmd_help.STATE"
        ) as mock_state:
            mock_config.RAFFLE_CHANNEL_ID = 333
            mock_config.TRICK_OR_TREAT_CHANNEL_ID = None
            mock_state.state = {"raffle_on": True}
            result = _build_activities_description(has_trick_or_treat=False)
        self.assertIn("<#333>", result)

    def test_appends_trick_or_treat_channel_when_enabled(self):
        with patch("ironforgedbot.commands.help.cmd_help.CONFIG") as mock_config, patch(
            "ironforgedbot.commands.help.cmd_help.STATE"
        ) as mock_state:
            mock_config.RAFFLE_CHANNEL_ID = 333
            mock_config.TRICK_OR_TREAT_CHANNEL_ID = 444
            mock_state.state = {"raffle_on": False}
            result = _build_activities_description(has_trick_or_treat=True)
        self.assertIn("<#444>", result)

    def test_no_trick_or_treat_channel_when_not_enabled(self):
        with patch("ironforgedbot.commands.help.cmd_help.CONFIG") as mock_config, patch(
            "ironforgedbot.commands.help.cmd_help.STATE"
        ) as mock_state:
            mock_config.RAFFLE_CHANNEL_ID = 333
            mock_config.TRICK_OR_TREAT_CHANNEL_ID = 444
            mock_state.state = {"raffle_on": False}
            result = _build_activities_description(has_trick_or_treat=False)
        self.assertNotIn("<#444>", result)
