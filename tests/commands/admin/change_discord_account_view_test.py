import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import discord
from discord.errors import Forbidden, HTTPException
from sqlalchemy.exc import IntegrityError

from ironforgedcore.common.ranks import RANK
from ironforgedcore.common.role_names import (
    BANNED_ROLE_NAME,
    BLACKLISTED_ROLE_NAME,
    BOOSTER_ROLE_NAME,
    PROSPECT_ROLE_NAME,
)
from ironforgedcore.common.roles import ROLE
from ironforgedcore.services.member_service import UniqueDiscordIdVolation
from tests.helpers import create_mock_discord_interaction, create_test_member


def _make_role(name: str) -> Mock:
    role = Mock(spec=discord.Role)
    role.name = name
    return role


def _make_member(
    member_id: int, display_name: str, roles: list[str], nick: str | None = None
) -> Mock:
    member = Mock(spec=discord.Member)
    member.id = member_id
    member.display_name = display_name
    member.nick = nick
    member.global_name = display_name
    member.mention = f"<@{member_id}>"
    member.roles = [_make_role(r) for r in roles]
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    member.edit = AsyncMock()
    return member


def _make_db_member(
    member_id: str, discord_id: int, nickname: str = "TestUser"
) -> Mock:
    member = Mock()
    member.id = member_id
    member.discord_id = discord_id
    member.nickname = nickname
    return member


class TestResolveTrackedRoles(unittest.TestCase):
    def test_returns_only_tracked_named_roles(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _resolve_tracked_discord_roles,
        )

        member = _make_member(
            1,
            "TestUser",
            [
                ROLE.MEMBER,
                RANK.MYTH,
                "Custom Decoration",
                BOOSTER_ROLE_NAME,
                PROSPECT_ROLE_NAME,
            ],
        )
        guild = Mock()

        result = _resolve_tracked_discord_roles(guild, member)
        names = sorted(r.name for r in result)
        self.assertEqual(
            names,
            sorted([ROLE.MEMBER, RANK.MYTH, BOOSTER_ROLE_NAME, PROSPECT_ROLE_NAME]),
        )


class TestBuildChangelogComment(unittest.TestCase):
    def test_basic_comment(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            StepResult,
            _build_changelog_comment,
        )

        old = _make_member(1, "OldUser", [ROLE.MEMBER])
        new = _make_member(2, "NewUser", [])
        step = StepResult(added_roles=["Member"], removed_roles=["Member"])

        comment = _build_changelog_comment(old, new, step)
        self.assertIn("from <@1> to <@2>", comment)
        self.assertIn("added 1 role", comment)
        self.assertIn("removed 1 role", comment)

    def test_long_comment_preserved_under_max(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            CHANGELOG_COMMENT_MAX_LENGTH,
            StepResult,
            _build_changelog_comment,
        )

        old = _make_member(1, "OldUser", [ROLE.MEMBER])
        new = _make_member(2, "NewUser", [])
        step = StepResult(
            added_roles=[f"Role{i}" for i in range(5)],
            removed_roles=[f"Role{i}" for i in range(5)],
            nick_set=True,
            nick_cleared=True,
            errors=["e1", "e2"],
        )

        comment = _build_changelog_comment(old, new, step)
        self.assertLessEqual(len(comment), CHANGELOG_COMMENT_MAX_LENGTH)

    def test_truncates_at_max_length(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            CHANGELOG_COMMENT_MAX_LENGTH,
            _build_changelog_comment,
        )

        class _LongStep:
            added_roles = [f"r{i}" for i in range(50)]
            removed_roles = [f"r{i}" for i in range(50)]
            errors = [f"e{i}" for i in range(50)]
            nick_set = True
            nick_cleared = True

            def to_changelog_lines(self):
                return [
                    "; ".join(
                        [f"added {self.added_roles} roles"]
                        + [f"removed {self.removed_roles} roles"]
                        + [f"set new nickname"]
                        + [f"cleared old nickname"]
                        + [f"{len(self.errors)} errors: " + ", ".join(self.errors)]
                    )
                ]

        old = _make_member(111111111111111111, "OldUser", [ROLE.MEMBER])
        new = _make_member(222222222222222222, "NewUser", [])

        comment = _build_changelog_comment(old, new, _LongStep())
        self.assertLessEqual(len(comment), CHANGELOG_COMMENT_MAX_LENGTH)
        self.assertTrue(comment.endswith("…"))


class TestChangeDiscordAccountView(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.guild = Mock(spec=discord.Guild)
        self.guild.roles = []
        self.report_channel = Mock(spec=discord.TextChannel)
        self.report_channel.send = AsyncMock()

        from ironforgedbot.commands.admin.change_discord_account_view import (
            ChangeDiscordAccountView,
        )

        self.view = ChangeDiscordAccountView(
            report_channel=self.report_channel,
            guild=self.guild,
        )

        self.old_user = _make_member(100, "OldUser", [ROLE.MEMBER, RANK.MYTH])
        self.new_user = _make_member(200, "NewUser", [])

        self.mock_interaction = create_mock_discord_interaction(
            user=create_test_member("AdminUser", [ROLE.LEADERSHIP])
        )
        self.mock_interaction.guild = self.guild
        self.mock_interaction.edit_original_response = AsyncMock()
        self.mock_interaction.original_response = AsyncMock(
            return_value=Mock(spec=discord.Message)
        )

    def _select(self, name: str, value: Mock):
        select = Mock(spec=discord.ui.UserSelect)
        select.values = [value]
        return select

    def test_continue_button_disabled_until_both_selected(self):
        continue_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_continue"
        )
        self.assertTrue(continue_btn.disabled)

        self.view.old_user = self.old_user
        self.view._sync_button_state()
        self.assertTrue(continue_btn.disabled)

        self.view.new_user = self.new_user
        self.view._sync_button_state()
        self.assertFalse(continue_btn.disabled)

    def test_continue_disabled_when_same_user_selected(self):
        self.view.old_user = self.old_user
        self.view.new_user = self.old_user
        self.view._sync_button_state()
        continue_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_continue"
        )
        self.assertTrue(continue_btn.disabled)

    async def test_old_account_select_updates_state(self):
        select = self.view.old_account_select
        with patch.object(
            type(select), "values", new_callable=PropertyMock
        ) as mock_vals:
            mock_vals.return_value = [self.old_user]
            await select.callback(self.mock_interaction)

        self.assertEqual(self.view.old_user, self.old_user)
        self.mock_interaction.response.edit_message.assert_called_once()

    async def test_new_account_select_clears_old_when_same_id(self):
        self.view.old_user = self.old_user
        select = self.view.new_account_select
        with patch.object(
            type(select), "values", new_callable=PropertyMock
        ) as mock_vals:
            mock_vals.return_value = [self.old_user]
            await select.callback(self.mock_interaction)

        self.assertIsNone(self.view.old_user)
        self.assertEqual(self.view.new_user, self.old_user)

    async def test_old_account_select_clears_new_when_same_id(self):
        self.view.new_user = self.new_user
        select = self.view.old_account_select
        with patch.object(
            type(select), "values", new_callable=PropertyMock
        ) as mock_vals:
            mock_vals.return_value = [self.new_user]
            await select.callback(self.mock_interaction)

        self.assertIsNone(self.view.new_user)
        self.assertEqual(self.view.old_user, self.new_user)

    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.create_member_service"
    )
    @patch("ironforgedbot.commands.admin.change_discord_account_view.db")
    async def test_continue_button_swaps_to_confirm_view(
        self, mock_db, mock_create_service
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        admin = Mock()
        admin.id = "admin-db-id"
        mock_service.get_member_by_discord_id = AsyncMock(return_value=admin)
        mock_create_service.return_value = mock_service

        self.view.old_user = self.old_user
        self.view.new_user = self.new_user

        continue_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_continue"
        )
        await continue_btn.callback(self.mock_interaction)

        self.mock_interaction.response.edit_message.assert_called_once()
        self.mock_interaction.edit_original_response.assert_called_once()
        kwargs = self.mock_interaction.edit_original_response.call_args.kwargs
        self.assertIn("view", kwargs)
        self.assertIn("embed", kwargs)

    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.create_member_service"
    )
    @patch("ironforgedbot.commands.admin.change_discord_account_view.db")
    async def test_continue_button_works_without_admin_db(
        self, mock_db, mock_create_service
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        mock_create_service.return_value = mock_service

        self.view.old_user = self.old_user
        self.view.new_user = self.new_user

        continue_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_continue"
        )
        await continue_btn.callback(self.mock_interaction)

        self.mock_interaction.edit_original_response.assert_called_once()


class TestChangeDiscordAccountConfirmView(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.guild = Mock(spec=discord.Guild)
        self.report_channel = Mock(spec=discord.TextChannel)
        self.report_channel.send = AsyncMock()

        self.old_user = _make_member(100, "OldUser", [ROLE.MEMBER, RANK.MYTH])
        self.new_user = _make_member(200, "NewUser", [])

        from ironforgedbot.commands.admin.change_discord_account_view import (
            ChangeDiscordAccountConfirmView,
        )

        self.view = ChangeDiscordAccountConfirmView(
            old_user=self.old_user,
            new_user=self.new_user,
            guild=self.guild,
            report_channel=self.report_channel,
            admin_db_id="admin-db-id",
        )

        self.mock_interaction = create_mock_discord_interaction(
            user=create_test_member("AdminUser", [ROLE.LEADERSHIP])
        )
        self.mock_interaction.edit_original_response = AsyncMock()

    def test_build_embed_lists_tracked_roles(self):
        embed = self.view.build_embed()
        self.assertIn("Adding roles", embed.description)
        self.assertIn("Removing roles", embed.description)
        self.assertIn(ROLE.MEMBER, embed.description)
        self.assertIn(RANK.MYTH, embed.description)
        self.assertIn("<@100>", embed.description)
        self.assertIn("<@200>", embed.description)

    def test_build_embed_shows_none_when_no_tracked_roles(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            ChangeDiscordAccountConfirmView,
        )

        old = _make_member(100, "OldUser", [])
        new = _make_member(200, "NewUser", [])
        view = ChangeDiscordAccountConfirmView(
            old_user=old,
            new_user=new,
            guild=self.guild,
            report_channel=self.report_channel,
            admin_db_id="admin-db-id",
        )
        embed = view.build_embed()
        self.assertIn("**Adding roles** (0): _none_", embed.description)
        self.assertIn("**Removing roles** (0): _none_", embed.description)

    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_old")
    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_new")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.create_member_service"
    )
    @patch("ironforgedbot.commands.admin.change_discord_account_view.db")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.member_update_emitter"
    )
    async def test_confirm_executes_full_swap(
        self,
        mock_emitter,
        mock_db,
        mock_create_service,
        mock_apply_new,
        mock_apply_old,
    ):
        from ironforgedbot.commands.admin.change_discord_account_view import StepResult

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        db_member = _make_db_member("member-uuid", 100, "TestUser")
        mock_service.get_member_by_discord_id = AsyncMock(side_effect=[db_member, None])
        mock_service.change_discord_id = AsyncMock(return_value=db_member)
        mock_create_service.return_value = mock_service

        mock_apply_new.return_value = StepResult(added_roles=["Member", "Myth"])
        mock_apply_old.return_value = StepResult(removed_roles=["Member", "Myth"])

        confirm_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_confirm"
        )
        await confirm_btn.callback(self.mock_interaction)

        mock_apply_new.assert_called_once()
        mock_apply_old.assert_called_once()
        mock_service.change_discord_id.assert_called_once()
        call_kwargs = mock_service.change_discord_id.call_args.kwargs
        self.assertEqual(call_kwargs["id"], "member-uuid")
        self.assertEqual(call_kwargs["new_discord_id"], 200)
        self.assertEqual(call_kwargs["admin_id"], "admin-db-id")
        self.assertIn("from <@100> to <@200>", call_kwargs["comment"])

        self.report_channel.send.assert_called_once()
        sent_text = self.report_channel.send.call_args.args[0]
        self.assertIsInstance(sent_text, str)
        self.assertTrue(sent_text.startswith(":bust_in_silhouette:"))
        self.assertIn("<@100>", sent_text)
        self.assertIn("<@200>", sent_text)
        self.assertNotIn("role(s)", sent_text)
        self.assertNotIn("nickname", sent_text)

        embed = self.mock_interaction.edit_original_response.call_args.kwargs["embed"]
        self.assertIn("<@100>", embed.description)
        self.assertIn("<@200>", embed.description)
        self.assertNotIn("role", embed.description.lower())
        self.assertNotIn("nickname", embed.description.lower())

    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_old")
    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_new")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.create_member_service"
    )
    @patch("ironforgedbot.commands.admin.change_discord_account_view.db")
    async def test_confirm_db_member_not_found(
        self, mock_db, mock_create_service, mock_apply_new, mock_apply_old
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        mock_create_service.return_value = mock_service

        confirm_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_confirm"
        )
        await confirm_btn.callback(self.mock_interaction)

        mock_apply_new.assert_not_called()
        mock_apply_old.assert_not_called()
        self.report_channel.send.assert_called_once()
        sent_text = self.report_channel.send.call_args.args[0]
        self.assertIn(":bust_in_silhouette:", sent_text)
        self.assertIn("reassign failed", sent_text)
        self.assertIn("OLD not linked to a DB member", sent_text)
        embed = self.mock_interaction.edit_original_response.call_args.kwargs["embed"]
        self.assertIn("Member not found", embed.title)

    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_old")
    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_new")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.create_member_service"
    )
    @patch("ironforgedbot.commands.admin.change_discord_account_view.db")
    async def test_confirm_collision_reports_error(
        self, mock_db, mock_create_service, mock_apply_new, mock_apply_old
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        db_member = _make_db_member("member-uuid", 100)
        other_member = _make_db_member("other-uuid", 200, "OtherUser")
        mock_service.get_member_by_discord_id = AsyncMock(
            side_effect=[db_member, other_member]
        )
        mock_create_service.return_value = mock_service

        confirm_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_confirm"
        )
        await confirm_btn.callback(self.mock_interaction)

        mock_apply_new.assert_not_called()
        mock_apply_old.assert_not_called()
        self.report_channel.send.assert_called_once()
        sent_text = self.report_channel.send.call_args.args[0]
        self.assertIn(":bust_in_silhouette:", sent_text)
        self.assertIn("reassign failed", sent_text)
        self.assertIn("OtherUser", sent_text)
        embed = self.mock_interaction.edit_original_response.call_args.kwargs["embed"]
        self.assertIn("already in use", embed.title)
        self.assertIn("OtherUser", embed.description)

    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_old")
    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_new")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.create_member_service"
    )
    @patch("ironforgedbot.commands.admin.change_discord_account_view.db")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.member_update_emitter"
    )
    async def test_confirm_db_swap_failure_after_discord_writes(
        self,
        mock_emitter,
        mock_db,
        mock_create_service,
        mock_apply_new,
        mock_apply_old,
    ):
        from ironforgedbot.commands.admin.change_discord_account_view import StepResult

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        db_member = _make_db_member("member-uuid", 100)
        mock_service.get_member_by_discord_id = AsyncMock(side_effect=[db_member, None])
        mock_service.change_discord_id = AsyncMock(
            side_effect=UniqueDiscordIdVolation("dup")
        )
        mock_create_service.return_value = mock_service

        mock_apply_new.return_value = StepResult(added_roles=["Member"])
        mock_apply_old.return_value = StepResult(removed_roles=["Member"])

        confirm_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_confirm"
        )
        await confirm_btn.callback(self.mock_interaction)

        self.report_channel.send.assert_called_once()
        sent_text = self.report_channel.send.call_args.args[0]
        self.assertIn(":bust_in_silhouette:", sent_text)
        self.assertIn("reassign failed", sent_text)
        self.assertIn("DB swap failed", sent_text)
        embed = self.mock_interaction.edit_original_response.call_args.kwargs["embed"]
        self.assertIn("DB swap failed", embed.title)
        self.assertIn("Re-run", embed.description)

    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_old")
    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_new")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.create_member_service"
    )
    @patch("ironforgedbot.commands.admin.change_discord_account_view.db")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.member_update_emitter"
    )
    async def test_confirm_db_integrity_error(
        self,
        mock_emitter,
        mock_db,
        mock_create_service,
        mock_apply_new,
        mock_apply_old,
    ):
        from ironforgedbot.commands.admin.change_discord_account_view import StepResult

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        db_member = _make_db_member("member-uuid", 100)
        mock_service.get_member_by_discord_id = AsyncMock(side_effect=[db_member, None])
        mock_service.change_discord_id = AsyncMock(
            side_effect=IntegrityError("stmt", None, Exception("dup"))
        )
        mock_create_service.return_value = mock_service

        mock_apply_new.return_value = StepResult(added_roles=["Member"])
        mock_apply_old.return_value = StepResult(removed_roles=["Member"])

        confirm_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_confirm"
        )
        await confirm_btn.callback(self.mock_interaction)

        self.report_channel.send.assert_called_once()
        sent_text = self.report_channel.send.call_args.args[0]
        self.assertIn(":bust_in_silhouette:", sent_text)
        self.assertIn("reassign failed", sent_text)
        self.assertIn("integrity error", sent_text)
        embed = self.mock_interaction.edit_original_response.call_args.kwargs["embed"]
        self.assertIn("integrity error", embed.title)

    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_old")
    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_new")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.create_member_service"
    )
    @patch("ironforgedbot.commands.admin.change_discord_account_view.db")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.member_update_emitter"
    )
    async def test_confirm_records_partial_errors(
        self,
        mock_emitter,
        mock_db,
        mock_create_service,
        mock_apply_new,
        mock_apply_old,
    ):
        from ironforgedbot.commands.admin.change_discord_account_view import StepResult

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        db_member = _make_db_member("member-uuid", 100)
        mock_service.get_member_by_discord_id = AsyncMock(side_effect=[db_member, None])
        mock_service.change_discord_id = AsyncMock(return_value=db_member)
        mock_create_service.return_value = mock_service

        mock_apply_new.return_value = StepResult(
            added_roles=["Member"],
            errors=["add_roles: Forbidden"],
        )
        mock_apply_old.return_value = StepResult(removed_roles=["Member"])

        confirm_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_confirm"
        )
        await confirm_btn.callback(self.mock_interaction)

        sent_text = self.report_channel.send.call_args.args[0]
        self.assertIsInstance(sent_text, str)
        self.assertTrue(sent_text.startswith(":bust_in_silhouette:"))
        self.assertIn("reassigned", sent_text)
        self.assertNotIn("role(s)", sent_text)
        self.assertNotIn("nickname", sent_text)
        embed = self.mock_interaction.edit_original_response.call_args.kwargs["embed"]
        self.assertIn("with errors", embed.title)
        self.assertIn("<@100>", embed.description)
        self.assertIn("<@200>", embed.description)
        self.assertNotIn("role", embed.description.lower())
        self.assertNotIn("nickname", embed.description.lower())

    async def test_confirm_disables_buttons_after_click(self):
        self.view.completed = False
        confirm_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_confirm"
        )

        with patch(
            "ironforgedbot.commands.admin.change_discord_account_view._apply_to_new",
            new=AsyncMock(
                return_value=Mock(added_roles=[], removed_roles=[], errors=[])
            ),
        ), patch(
            "ironforgedbot.commands.admin.change_discord_account_view._apply_to_old",
            new=AsyncMock(
                return_value=Mock(added_roles=[], removed_roles=[], errors=[])
            ),
        ), patch(
            "ironforgedbot.commands.admin.change_discord_account_view.create_member_service",
            new=MagicMock(),
        ), patch(
            "ironforgedbot.commands.admin.change_discord_account_view.db",
            new=Mock(get_session=AsyncMock()),
        ):
            await confirm_btn.callback(self.mock_interaction)

        self.assertTrue(self.view.completed)
        for child in self.view.children:
            if isinstance(child, discord.ui.Item):
                self.assertTrue(child.disabled)

    async def test_confirm_twice_is_noop(self):
        self.view.completed = True
        confirm_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_confirm"
        )
        await confirm_btn.callback(self.mock_interaction)
        self.mock_interaction.followup.send.assert_not_called()

    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_old")
    @patch("ironforgedbot.commands.admin.change_discord_account_view._apply_to_new")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.create_member_service"
    )
    @patch("ironforgedbot.commands.admin.change_discord_account_view.db")
    @patch(
        "ironforgedbot.commands.admin.change_discord_account_view.member_update_emitter"
    )
    async def test_confirm_does_not_send_working_message(
        self,
        mock_emitter,
        mock_db,
        mock_create_service,
        mock_apply_new,
        mock_apply_old,
    ):
        from ironforgedbot.commands.admin.change_discord_account_view import StepResult

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_db.get_session.return_value = mock_session

        mock_service = MagicMock()
        mock_service.get_member_by_discord_id = AsyncMock(return_value=None)
        mock_create_service.return_value = mock_service

        confirm_btn = next(
            c
            for c in self.view.children
            if isinstance(c, discord.ui.Button)
            and c.custom_id == "change_discord_confirm"
        )
        await confirm_btn.callback(self.mock_interaction)

        self.mock_interaction.followup.send.assert_not_called()
        self.mock_interaction.edit_original_response.assert_called_once()


class TestApplyToNew(unittest.IsolatedAsyncioTestCase):
    async def test_adds_missing_tracked_roles(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER, RANK.MYTH])
        new = _make_member(2, "New", [])

        result = await _apply_to_new(old, new, "TestUser")

        self.assertIn(ROLE.MEMBER, result.added_roles)
        self.assertIn(RANK.MYTH, result.added_roles)
        new.add_roles.assert_called_once()

    async def test_uses_atomic_false_for_single_event(self):
        """atomic=False makes add_roles a single HTTP call → single Guild
        Member Update event, so a single suppression catches it."""
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER, RANK.MYTH])
        new = _make_member(2, "New", [])

        await _apply_to_new(old, new, "TestUser")

        _, kwargs = new.add_roles.call_args
        self.assertFalse(kwargs.get("atomic", True))

    async def test_resuppresses_after_writes(self):
        """Re-suppress after each write to cover cascade events from handler
        rollbacks (e.g. NicknameChangeHandler._rollback)."""
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        with patch(
            "ironforgedbot.commands.admin.change_discord_account_view.member_update_emitter"
        ) as mock_emitter:
            old = _make_member(1, "Old", [ROLE.MEMBER, RANK.MYTH])
            new = _make_member(2, "DifferentNick", [])

            result = await _apply_to_new(old, new, "TestUser")

        self.assertGreaterEqual(mock_emitter.suppress_next_for.call_count, 2)
        self.assertIn(ROLE.MEMBER, result.added_roles)
        self.assertIn(RANK.MYTH, result.added_roles)
        new.add_roles.assert_called_once()

    async def test_skips_roles_already_on_new(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER, RANK.MYTH])
        new = _make_member(2, "New", [ROLE.MEMBER, RANK.MYTH, ROLE.STAFF])

        result = await _apply_to_new(old, new, "TestUser")

        self.assertEqual(result.added_roles, [])
        new.add_roles.assert_not_called()

    async def test_sets_nickname_when_different(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        old = _make_member(1, "Old", [])
        new = _make_member(2, "CurrentName", [])

        result = await _apply_to_new(old, new, "TestUser")

        new.edit.assert_called_once()
        self.assertTrue(result.nick_set)

    async def test_skips_nickname_when_already_matches(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        old = _make_member(1, "Old", [])
        new = _make_member(2, "TestUser", [])

        result = await _apply_to_new(old, new, "TestUser")

        new.edit.assert_not_called()
        self.assertFalse(result.nick_set)

    async def test_captures_forbidden_error(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER])
        new = _make_member(2, "New", [])
        new.add_roles.side_effect = Forbidden(Mock(), "forbidden")

        result = await _apply_to_new(old, new, "TestUser")

        self.assertEqual(result.added_roles, [])
        self.assertTrue(any("add_roles" in e for e in result.errors))

    async def test_captures_http_exception(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER])
        new = _make_member(2, "New", [])
        new.edit.side_effect = HTTPException(Mock(), "http error")

        result = await _apply_to_new(old, new, "DifferentName")

        self.assertFalse(result.nick_set)
        self.assertTrue(any("set_nickname" in e for e in result.errors))

    async def test_add_roles_retries_on_transient_503_then_succeeds(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER])
        new = _make_member(2, "New", [])
        resp = Mock()
        resp.status = 503
        new.add_roles.side_effect = [
            HTTPException(resp, {"code": 0, "message": "Service Unavailable"}),
            None,
        ]

        with patch("ironforgedbot.common.discord_retry.asyncio.sleep", new=AsyncMock()):
            result = await _apply_to_new(old, new, "TestUser")

        self.assertEqual(result.errors, [])
        self.assertIn(ROLE.MEMBER, result.added_roles)
        self.assertEqual(new.add_roles.await_count, 2)

    async def test_add_roles_does_not_retry_on_forbidden(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )
        from discord.errors import Forbidden

        old = _make_member(1, "Old", [ROLE.MEMBER])
        new = _make_member(2, "New", [])
        new.add_roles.side_effect = Forbidden(Mock(), "nope")

        result = await _apply_to_new(old, new, "TestUser")

        self.assertTrue(any("add_roles" in e for e in result.errors))
        self.assertEqual(new.add_roles.await_count, 1)

    async def test_add_roles_gives_up_after_persistent_503(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_new,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER])
        new = _make_member(2, "New", [])
        resp = Mock()
        resp.status = 503
        new.add_roles.side_effect = HTTPException(
            resp, {"code": 0, "message": "Service Unavailable"}
        )

        with patch("ironforgedbot.common.discord_retry.asyncio.sleep", new=AsyncMock()):
            result = await _apply_to_new(old, new, "TestUser")

        self.assertTrue(any("add_roles" in e for e in result.errors))
        self.assertEqual(new.add_roles.await_count, 3)


class TestApplyToOld(unittest.IsolatedAsyncioTestCase):
    async def test_removes_tracked_roles(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_old,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER, RANK.MYTH, BOOSTER_ROLE_NAME])
        new = _make_member(2, "New", [])

        result = await _apply_to_old(old, new)

        self.assertIn(ROLE.MEMBER, result.removed_roles)
        self.assertIn(RANK.MYTH, result.removed_roles)
        self.assertIn(BOOSTER_ROLE_NAME, result.removed_roles)
        old.remove_roles.assert_called_once()

    async def test_uses_atomic_false_for_single_event(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_old,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER, RANK.MYTH])
        new = _make_member(2, "New", [])

        await _apply_to_old(old, new)

        _, kwargs = old.remove_roles.call_args
        self.assertFalse(kwargs.get("atomic", True))

    async def test_resuppresses_after_writes(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_old,
        )

        with patch(
            "ironforgedbot.commands.admin.change_discord_account_view.member_update_emitter"
        ) as mock_emitter:
            old = _make_member(1, "Old", [ROLE.MEMBER], nick="OldNick")
            new = _make_member(2, "New", [])

            await _apply_to_old(old, new)

        self.assertGreaterEqual(mock_emitter.suppress_next_for.call_count, 2)

    async def test_clears_nickname_when_present(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_old,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER], nick="OldNick")
        new = _make_member(2, "New", [])

        result = await _apply_to_old(old, new)

        old.edit.assert_called_once_with(
            nick=None, reason="Clan nickname migrated to new Discord account"
        )
        self.assertTrue(result.nick_cleared)

    async def test_skips_nickname_when_already_none(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_old,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER], nick=None)
        new = _make_member(2, "New", [])

        result = await _apply_to_old(old, new)

        old.edit.assert_not_called()
        self.assertFalse(result.nick_cleared)

    async def test_captures_forbidden_on_role_removal(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_old,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER])
        new = _make_member(2, "New", [])
        old.remove_roles.side_effect = Forbidden(Mock(), "nope")

        result = await _apply_to_old(old, new)

        self.assertEqual(result.removed_roles, [])
        self.assertTrue(any("remove_roles" in e for e in result.errors))


class TestBuildChannelReport(unittest.TestCase):
    def test_success_default_format(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _build_channel_report,
        )

        old = _make_member(100, "OldUser", [ROLE.MEMBER])
        new = _make_member(200, "NewUser", [])

        text = _build_channel_report(old, new)
        self.assertEqual(
            text,
            ":bust_in_silhouette: **Discord account reassigned:** " "<@100> → <@200>",
        )

    def test_failed_label_and_reason(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _build_channel_report,
        )

        old = _make_member(100, "OldUser", [ROLE.MEMBER])
        new = _make_member(200, "NewUser", [])

        text = _build_channel_report(
            old,
            new,
            label="reassign failed",
            reason="NEW already linked to **OtherUser**",
        )
        self.assertEqual(
            text,
            ":bust_in_silhouette: **Discord account reassign failed:** "
            "<@100> → <@200> — NEW already linked to **OtherUser**",
        )

    def test_label_only_no_reason(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _build_channel_report,
        )

        old = _make_member(100, "OldUser", [])
        new = _make_member(200, "NewUser", [])

        text = _build_channel_report(old, new, label="reassign failed")
        self.assertEqual(
            text,
            ":bust_in_silhouette: **Discord account reassign failed:** "
            "<@100> → <@200>",
        )

    async def test_remove_roles_retries_on_transient_503_then_succeeds(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_old,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER])
        new = _make_member(2, "New", [])
        resp = Mock()
        resp.status = 503
        old.remove_roles.side_effect = [
            HTTPException(resp, {"code": 0, "message": "Service Unavailable"}),
            None,
        ]

        with patch("ironforgedbot.common.discord_retry.asyncio.sleep", new=AsyncMock()):
            result = await _apply_to_old(old, new)

        self.assertEqual(result.errors, [])
        self.assertIn(ROLE.MEMBER, result.removed_roles)
        self.assertEqual(old.remove_roles.await_count, 2)

    async def test_remove_roles_gives_up_after_persistent_503(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            _apply_to_old,
        )

        old = _make_member(1, "Old", [ROLE.MEMBER])
        new = _make_member(2, "New", [])
        resp = Mock()
        resp.status = 503
        old.remove_roles.side_effect = HTTPException(
            resp, {"code": 0, "message": "Service Unavailable"}
        )

        with patch("ironforgedbot.common.discord_retry.asyncio.sleep", new=AsyncMock()):
            result = await _apply_to_old(old, new)

        self.assertTrue(any("remove_roles" in e for e in result.errors))
        self.assertEqual(old.remove_roles.await_count, 3)


class TestCmdChangeDiscordAccount(unittest.IsolatedAsyncioTestCase):
    async def test_sends_view_message(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            cmd_change_discord_account,
        )

        guild = Mock(spec=discord.Guild)
        report_channel = Mock(spec=discord.TextChannel)

        interaction = create_mock_discord_interaction(
            user=create_test_member("Admin", [ROLE.LEADERSHIP])
        )
        interaction.guild = guild
        interaction.original_response = AsyncMock(
            return_value=Mock(spec=discord.Message)
        )

        await cmd_change_discord_account(interaction, report_channel)

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()
        kwargs = interaction.followup.send.call_args.kwargs
        self.assertIn("view", kwargs)
        self.assertIn("embed", kwargs)
        self.assertTrue(kwargs.get("ephemeral"))

    async def test_returns_silently_without_guild(self):
        from ironforgedbot.commands.admin.change_discord_account_view import (
            cmd_change_discord_account,
        )

        interaction = Mock()
        interaction.guild = None

        await cmd_change_discord_account(interaction, Mock())
        interaction.followup.send.assert_not_called()
