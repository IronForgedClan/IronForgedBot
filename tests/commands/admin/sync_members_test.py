import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedbot.common.roles import (
    ROLE,
    BOOSTER_ROLE_NAME,
    PROSPECT_ROLE_NAME,
    BLACKLISTED_ROLE_NAME,
    BANNED_ROLE_NAME,
)
from ironforgedbot.models.member import Member
from ironforgedbot.services.member_service import (
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)
from tests.helpers import (
    create_mock_discord_interaction,
    create_mock_discord_role,
    create_test_member,
    create_test_db_member,
    setup_database_service_mocks,
)

with patch(
    "ironforgedbot.common.helpers.normalize_discord_string", side_effect=lambda x: x
):
    from ironforgedbot.commands.admin.sync_members import sync_members


class TestSyncMembers(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.guild = Mock(spec=discord.Guild)
        self.test_member1 = create_test_member("TestUser1", [ROLE.MEMBER], "testuser1")
        self.test_member1.id = 1001
        self.test_member2 = create_test_member("TestUser2", [ROLE.MEMBER], "testuser2")
        self.test_member2.id = 1002
        self.test_member3 = create_test_member("TestUser3", [ROLE.MEMBER], "testuser3")
        self.test_member3.id = 1003

        self.db_member1 = create_test_db_member(
            nickname="testuser1",
            discord_id=1001,
            rank=RANK.IRON,
            ingots=100,
            id=1,
            role=ROLE.MEMBER,
        )
        self.db_member2 = create_test_db_member(
            nickname="oldnick",
            discord_id=1002,
            rank=RANK.IRON,
            ingots=200,
            id=2,
            role=ROLE.MEMBER,
        )
        self.db_member3 = create_test_db_member(
            nickname="leftuser",
            discord_id=9999,
            rank=RANK.IRON,
            ingots=300,
            id=3,
            role=ROLE.MEMBER,
        )

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_disable_missing_members(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member1, self.test_member2]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = [
                self.db_member1,
                self.db_member2,
                self.db_member3,
            ]
            result = await sync_members(self.guild)

        mock_service.disable_member.assert_called_once_with(3)
        self.assertIn(["leftuser", "Disabled", "No longer a member"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_nickname_change(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member2]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = [self.db_member2]
            result = await sync_members(self.guild)

        mock_service.change_nickname.assert_called_once_with(2, "testuser2")
        self.assertIn(["testuser2", "Updated", "Nickname changed "], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_nickname_change_unique_violation(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member2]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member2]
        mock_service.change_nickname.side_effect = UniqueNicknameViolation()

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        self.assertIn(["TestUser2", "Error", "Unique nickname violation"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_rank_change(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.MITHRIL
        mock_get_role.return_value = ROLE.MEMBER

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member1]

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_service.change_rank.assert_called_once_with(1, RANK.MITHRIL)
        self.assertIn(["testuser1", "Updated", "Rank changed"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_god_alignment_to_god_rank(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = GOD_ALIGNMENT.SARADOMIN

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member1]

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_service.change_rank.assert_called_once_with(1, RANK.GOD)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_add_new_member(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_service.create_member.assert_called_once_with(1003, "testuser3", RANK.IRON)
        self.assertIn(["testuser3", "Added", "New member created"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_no_nickname_error(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        member_no_nick = create_test_member("NoNick", [ROLE.MEMBER], None)
        member_no_nick.id = 1004
        member_no_nick.nick = None

        self.guild.members = [member_no_nick]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        self.assertIn(["", "Error", "No nickname"], result)
        mock_service.create_member.assert_not_called()

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_reactivate_disabled_member(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        disabled_member = Member(
            id=4,
            discord_id=1003,
            nickname="testuser3",
            rank=RANK.IRON,
            ingots=0,
            active=False,
        )

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.side_effect = UniqueDiscordIdVolation()
        mock_service.get_member_by_discord_id.return_value = disabled_member

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_service.reactivate_member.assert_called_once_with(
            4, "testuser3", RANK.IRON
        )
        self.assertIn(["testuser3", "Enabled", "Returning member"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_reactivate_nickname_dupe_error(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        disabled_member = Member(
            id=4,
            discord_id=1003,
            nickname="testuser3",
            rank=RANK.IRON,
            ingots=0,
            active=False,
        )

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.side_effect = UniqueDiscordIdVolation()
        mock_service.get_member_by_discord_id.return_value = disabled_member
        mock_service.reactivate_member.side_effect = UniqueNicknameViolation()

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        self.assertIn(["[D]TestUser3", "Error", "Nickname dupe"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_data_continuity_error(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        active_member = Member(
            id=4,
            discord_id=1003,
            nickname="testuser3",
            rank=RANK.IRON,
            ingots=0,
            active=True,
        )

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.side_effect = UniqueDiscordIdVolation()
        mock_service.get_member_by_discord_id.return_value = active_member

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        self.assertIn(["testuser3", "Error", "Data continuity error"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch("ironforgedbot.commands.admin.sync_members.logger")
    async def test_sync_members_uncaught_exception(
        self, mock_logger, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.side_effect = Exception("Database error")

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_logger.error.assert_called_once()
        self.assertIn(["testuser3", "Error", "Uncaught exception"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_no_rank_defaults_to_iron(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = None

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_service.create_member.assert_called_once_with(1003, "testuser3", RANK.IRON)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_skip_non_members(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        non_member = create_test_member("NonMember", [ROLE.GUEST], "nonmember")
        non_member.id = 1005

        self.guild.members = [self.test_member1, non_member]
        mock_check_role.side_effect = lambda member, role: member.id != 1005
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member1]

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_service.create_member.assert_not_called()
        self.assertEqual(len([r for r in result if "nonmember" in r[0].lower()]), 0)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_nickname_and_rank_change_combined(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        self.guild.members = [self.test_member2]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.MITHRIL
        mock_get_role.return_value = ROLE.MEMBER

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = [self.db_member2]

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_service.change_nickname.assert_called_once_with(2, "testuser2")
        mock_service.change_rank.assert_called_once_with(2, RANK.MITHRIL)
        self.assertIn(["testuser2", "Updated", "Nickname changed Rank changed"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_output_sorted_by_nickname(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        member_z = create_test_member("ZUser", [ROLE.MEMBER], "zuser")
        member_z.id = 1006
        member_a = create_test_member("AUser", [ROLE.MEMBER], "auser")
        member_a.id = 1007

        self.guild.members = [member_z, member_a]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        nicknames = [r[0] for r in result]
        self.assertEqual(nicknames, sorted(nicknames))

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_flag_change_booster(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that booster flag is synced when Discord role changes."""
        # Add booster role to Discord member
        booster_role = create_mock_discord_role(BOOSTER_ROLE_NAME)
        self.test_member1.roles.append(booster_role)
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        # DB member has is_booster=False
        self.db_member1.is_booster = False
        self.db_member1.is_prospect = False
        self.db_member1.is_blacklisted = False
        self.db_member1.is_banned = False

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = [self.db_member1]
            result = await sync_members(self.guild)

        mock_service.update_member_flags.assert_called_once_with(
            self.db_member1.id,
            is_booster=True,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        self.assertTrue(
            any("Flags: Booster: True" in r[2] for r in result if len(r) > 2)
        )

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_flag_change_prospect(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that prospect flag is synced when Discord role changes."""
        prospect_role = create_mock_discord_role(PROSPECT_ROLE_NAME)
        self.test_member1.roles.append(prospect_role)
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        self.db_member1.is_booster = False
        self.db_member1.is_prospect = False
        self.db_member1.is_blacklisted = False
        self.db_member1.is_banned = False

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = [self.db_member1]
            result = await sync_members(self.guild)

        mock_service.update_member_flags.assert_called_once_with(
            self.db_member1.id,
            is_booster=False,
            is_prospect=True,
            is_blacklisted=False,
            is_banned=False,
        )
        self.assertTrue(
            any("Flags: Prospect: True" in r[2] for r in result if len(r) > 2)
        )

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_flag_change_blacklisted(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that blacklisted flag is synced when Discord role changes."""
        blacklisted_role = create_mock_discord_role(BLACKLISTED_ROLE_NAME)
        self.test_member1.roles.append(blacklisted_role)
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        self.db_member1.is_booster = False
        self.db_member1.is_prospect = False
        self.db_member1.is_blacklisted = False
        self.db_member1.is_banned = False

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = [self.db_member1]
            result = await sync_members(self.guild)

        mock_service.update_member_flags.assert_called_once_with(
            self.db_member1.id,
            is_booster=False,
            is_prospect=False,
            is_blacklisted=True,
            is_banned=False,
        )
        self.assertTrue(
            any("Flags: Blacklisted: True" in r[2] for r in result if len(r) > 2)
        )

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_flag_change_banned(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that banned flag is synced when Discord role changes."""
        banned_role = create_mock_discord_role(BANNED_ROLE_NAME)
        self.test_member1.roles.append(banned_role)
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        self.db_member1.is_booster = False
        self.db_member1.is_prospect = False
        self.db_member1.is_blacklisted = False
        self.db_member1.is_banned = False

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = [self.db_member1]
            result = await sync_members(self.guild)

        mock_service.update_member_flags.assert_called_once_with(
            self.db_member1.id,
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=True,
        )
        self.assertTrue(
            any("Flags: Banned: True" in r[2] for r in result if len(r) > 2)
        )

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_multiple_flag_changes(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that multiple flags can change at once."""
        booster_role = create_mock_discord_role(BOOSTER_ROLE_NAME)
        prospect_role = create_mock_discord_role(PROSPECT_ROLE_NAME)
        self.test_member1.roles.extend([booster_role, prospect_role])
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        self.db_member1.is_booster = False
        self.db_member1.is_prospect = False
        self.db_member1.is_blacklisted = False
        self.db_member1.is_banned = False

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = [self.db_member1]
            result = await sync_members(self.guild)

        mock_service.update_member_flags.assert_called_once_with(
            self.db_member1.id,
            is_booster=True,
            is_prospect=True,
            is_blacklisted=False,
            is_banned=False,
        )
        # Check both flags are mentioned in output
        matching_results = [r for r in result if len(r) > 2 and "Flags:" in r[2]]
        self.assertEqual(len(matching_results), 1)
        self.assertIn("Booster: True", matching_results[0][2])
        self.assertIn("Prospect: True", matching_results[0][2])

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_flags_no_change(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that no flag update is called when flags already match."""
        self.guild.members = [self.test_member1]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        # DB member flags match Discord (no flag roles)
        self.db_member1.is_booster = False
        self.db_member1.is_prospect = False
        self.db_member1.is_blacklisted = False
        self.db_member1.is_banned = False

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = [self.db_member1]
            result = await sync_members(self.guild)

        mock_service.update_member_flags.assert_not_called()
        # Should not have any output since nothing changed
        self.assertEqual(len(result), 0)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_new_member_with_flags(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that new members get their flags set on creation."""
        # Add booster role to new Discord member
        booster_role = create_mock_discord_role(BOOSTER_ROLE_NAME)
        self.test_member3.roles.append(booster_role)
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_new_member = Mock()
        mock_new_member.id = "new-member-id"

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.return_value = mock_new_member

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_service.create_member.assert_called_once_with(1003, "testuser3", RANK.IRON)
        mock_service.update_member_flags.assert_called_once_with(
            "new-member-id",
            is_booster=True,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        self.assertIn(["testuser3", "Added", "New member created"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    async def test_sync_members_reactivated_member_with_flags(
        self, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that reactivated members get their flags synced."""
        # Add prospect role to returning Discord member
        prospect_role = create_mock_discord_role(PROSPECT_ROLE_NAME)
        self.test_member3.roles.append(prospect_role)
        self.guild.members = [self.test_member3]
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        disabled_member = Member(
            id=4,
            discord_id=1003,
            nickname="testuser3",
            rank=RANK.IRON,
            ingots=0,
            active=False,
        )

        mock_service = AsyncMock()
        mock_service.get_all_active_members.return_value = []
        mock_service.create_member.side_effect = UniqueDiscordIdVolation()
        mock_service.get_member_by_discord_id.return_value = disabled_member

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService",
            return_value=mock_service,
        ):
            result = await sync_members(self.guild)

        mock_service.reactivate_member.assert_called_once_with(
            4, "testuser3", RANK.IRON
        )
        mock_service.update_member_flags.assert_called_once_with(
            4,
            is_booster=False,
            is_prospect=True,
            is_blacklisted=False,
            is_banned=False,
        )
        self.assertIn(["testuser3", "Enabled", "Returning member"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_inactive_member_flag_update(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that inactive members in guild get their flags synced."""
        # Create a non-member Discord user (won't be processed as active member)
        inactive_discord_member = create_test_member(
            "InactiveUser", [ROLE.GUEST], "inactiveuser"
        )
        inactive_discord_member.id = 9999

        self.guild.members = [inactive_discord_member]
        # This member doesn't have ROLE.MEMBER, so check_member_has_role returns False
        mock_check_role.return_value = False
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        # Create inactive DB member with is_banned=True
        inactive_member = create_test_db_member(
            nickname="inactiveuser",
            discord_id=9999,
            rank=RANK.IRON,
            ingots=100,
            id=10,
            role=ROLE.MEMBER,
            active=False,
            is_banned=True,
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
        )

        # Set up guild.get_member to return the Discord member for this inactive member
        self.guild.get_member = Mock(return_value=inactive_discord_member)

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = []
            mock_service.get_all_inactive_members.return_value = [inactive_member]
            result = await sync_members(self.guild)

        # Should update flags because is_banned changed from True to False
        mock_service.update_member_flags.assert_called_once_with(
            10,
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        self.assertIn(["inactiveuser", "Inactive Updated", "Banned: False"], result)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_inactive_member_not_in_guild_skipped(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that inactive members not in guild are skipped."""
        self.guild.members = []
        mock_check_role.return_value = True
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        inactive_member = create_test_db_member(
            nickname="leftuser",
            discord_id=9999,
            rank=RANK.IRON,
            ingots=100,
            id=10,
            role=ROLE.MEMBER,
            active=False,
            is_banned=True,
        )

        # guild.get_member returns None for members not in guild
        self.guild.get_member = Mock(return_value=None)

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = []
            mock_service.get_all_inactive_members.return_value = [inactive_member]
            result = await sync_members(self.guild)

        # Should not update flags for member not in guild
        mock_service.update_member_flags.assert_not_called()
        self.assertEqual(len(result), 0)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_inactive_member_no_flag_changes_skipped(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test that inactive members with matching flags are not updated."""
        # Create a non-member Discord user (won't be processed as active member)
        inactive_discord_member = create_test_member(
            "InactiveUser", [ROLE.GUEST], "inactiveuser"
        )
        inactive_discord_member.id = 9999

        self.guild.members = [inactive_discord_member]
        # This member doesn't have ROLE.MEMBER, so check_member_has_role returns False
        mock_check_role.return_value = False
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        # DB member flags match Discord (no flag roles on Discord member)
        inactive_member = create_test_db_member(
            nickname="inactiveuser",
            discord_id=9999,
            rank=RANK.IRON,
            ingots=100,
            id=10,
            role=ROLE.MEMBER,
            active=False,
            is_banned=False,
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
        )

        self.guild.get_member = Mock(return_value=inactive_discord_member)

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = []
            mock_service.get_all_inactive_members.return_value = [inactive_member]
            result = await sync_members(self.guild)

        # Should not update flags when they match
        mock_service.update_member_flags.assert_not_called()
        self.assertEqual(len(result), 0)

    @patch("ironforgedbot.commands.admin.sync_members.db")
    @patch("ironforgedbot.commands.admin.sync_members.check_member_has_role")
    @patch("ironforgedbot.commands.admin.sync_members.get_rank_from_member")
    @patch(
        "ironforgedbot.commands.admin.sync_members.get_highest_privilage_role_from_member"
    )
    async def test_sync_members_inactive_member_multiple_flag_changes(
        self, mock_get_role, mock_get_rank, mock_check_role, mock_db
    ):
        """Test inactive member with multiple flag changes."""
        # Create a non-member Discord user with booster role
        inactive_discord_member = create_test_member(
            "InactiveUser", [ROLE.GUEST], "inactiveuser"
        )
        inactive_discord_member.id = 9999
        # Add booster role
        booster_role = create_mock_discord_role(BOOSTER_ROLE_NAME)
        inactive_discord_member.roles.append(booster_role)

        self.guild.members = [inactive_discord_member]
        # This member doesn't have ROLE.MEMBER, so check_member_has_role returns False
        mock_check_role.return_value = False
        mock_get_rank.return_value = RANK.IRON
        mock_get_role.return_value = ROLE.MEMBER

        # DB member has is_banned=True, is_booster=False
        inactive_member = create_test_db_member(
            nickname="inactiveuser",
            discord_id=9999,
            rank=RANK.IRON,
            ingots=100,
            id=10,
            role=ROLE.MEMBER,
            active=False,
            is_banned=True,
            is_booster=False,
            is_prospect=False,
            is_blacklisted=False,
        )

        self.guild.get_member = Mock(return_value=inactive_discord_member)

        with patch(
            "ironforgedbot.commands.admin.sync_members.MemberService"
        ) as mock_member_service_class:
            mock_session, mock_service = setup_database_service_mocks(
                mock_db, mock_member_service_class
            )
            mock_service.get_all_active_members.return_value = []
            mock_service.get_all_inactive_members.return_value = [inactive_member]
            result = await sync_members(self.guild)

        mock_service.update_member_flags.assert_called_once_with(
            10,
            is_booster=True,
            is_prospect=False,
            is_blacklisted=False,
            is_banned=False,
        )
        # Check both changes are mentioned in output
        matching_results = [
            r for r in result if len(r) > 2 and "Inactive Updated" in r[1]
        ]
        self.assertEqual(len(matching_results), 1)
        self.assertIn("Booster: True", matching_results[0][2])
        self.assertIn("Banned: False", matching_results[0][2])
