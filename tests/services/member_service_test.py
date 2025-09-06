from datetime import datetime, timedelta
from ssl import RAND_add
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

from ironforgedbot.common.ranks import RANK
from ironforgedbot.models.changelog import ChangeType, Changelog
from ironforgedbot.models.member import Member
from ironforgedbot.services.member_service import (
    MemberNotFoundException,
    MemberService,
    MemberServiceReactivateResponse,
    UniqueDiscordIdVolation,
    UniqueNicknameViolation,
)


class TestMemberService_CreateMember(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.services.member_service.datetime")
    async def test_should_create_member(self, mock_datetime) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        service = MemberService(db=mock_db)

        expected_member = {"discord_id": 12345, "nickname": "zezima"}

        result: Member = await service.create_member(
            int(expected_member["discord_id"]), str(expected_member["nickname"])
        )

        expected_changelog = {
            "member_id": result.id,
            "admin_id": None,
            "change_type": ChangeType.ADD_MEMBER,
            "previous_value": None,
            "new_value": None,
            "comment": "Added member",
            "timestamp": now,
        }

        result_member = mock_db.add.call_args_list[0][0][0]
        result_changelog = mock_db.add.call_args_list[1][0][0]

        self.assertEqual(mock_db.add.call_count, 2)

        self.assertIsInstance(result_member, Member)
        self.assertIsInstance(result_changelog, Changelog)
        for key, value in expected_changelog.items():
            actual_value = getattr(result_changelog, key, None)
            self.assertEqual(
                actual_value, value, f"Expected {key}={value}, but got {actual_value}"
            )

        expected_member["id"] = result.id
        self.assertIsInstance(result_member, Member)
        for key, value in expected_member.items():
            actual_value = getattr(result_member, key, None)
            self.assertEqual(
                actual_value, value, f"Expected {key}={value}, but got {actual_value}"
            )

        mock_db.commit.assert_called()

    async def test_rollback_raises_UniqueDiscordIdViolation_when_create_member_if_IntegrityError(
        self,
    ) -> None:
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock(
            side_effect=IntegrityError("discord_id", None, Exception())
        )
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        service = MemberService(db=mock_db)

        with self.assertRaises(UniqueDiscordIdVolation):
            await service.create_member(123, "test")

        mock_db.rollback.assert_awaited_once()

    async def test_rollback_raises_UniqueNicknameViolation_when_create_member_if_IntegrityError(
        self,
    ) -> None:
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock(
            side_effect=IntegrityError("nickname", None, Exception())
        )
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        service = MemberService(db=mock_db)

        with self.assertRaises(UniqueNicknameViolation):
            await service.create_member(123, "test")

        mock_db.rollback.assert_awaited_once()

    async def test_rollback_when_create_member_if_unhandled_exception(self) -> None:
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock(side_effect=Exception("unhandled exception"))
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        service = MemberService(db=mock_db)

        with self.assertRaises(Exception):
            await service.create_member(123, "test")

        mock_db.rollback.assert_awaited_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_should_succeed(self, mock_datetime) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        previous_joined_date = (now - timedelta(days=20),)
        mock_datetime.now.return_value = now

        old_member = Member(
            id="123",
            discord_id="333",
            active=False,
            nickname="zezima",
            ingots=2277,
            rank=RANK.IRON,
            joined_date=previous_joined_date,
            last_changed_date=now - timedelta(hours=1),
        )

        expected_member = {
            "id": old_member.id,
            "discord_id": old_member.discord_id,
            "active": True,
            "nickname": old_member.nickname,
            "ingots": old_member.ingots,
            "rank": old_member.rank,
            "joined_date": now,
            "last_changed_date": now,
        }

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        service = MemberService(db=mock_db)

        with patch.object(MemberService, "get_member_by_id", return_value=old_member):
            result: MemberServiceReactivateResponse = await service.reactivate_member(
                old_member.id,
                old_member.nickname,
            )

        expected_changelog_activity = {
            "member_id": old_member.id,
            "admin_id": None,
            "change_type": ChangeType.ACTIVITY_CHANGE,
            "previous_value": False,
            "new_value": True,
            "comment": "Returning member",
            "timestamp": now,
        }
        expected_changelog_join_date = {
            "member_id": old_member.id,
            "admin_id": None,
            "change_type": ChangeType.JOINED_DATE_CHANGE,
            "previous_value": previous_joined_date,
            "new_value": now,
            "comment": "Join date updated during reactivation",
            "timestamp": now,
        }

        result_changelog_activity = mock_db.add.call_args_list[0][0][0]
        result_changelog_join_date = mock_db.add.call_args_list[1][0][0]

        self.assertEqual(mock_db.add.call_count, 2)

        self.assertIsInstance(result_changelog_activity, Changelog)
        self.assertIsInstance(result_changelog_join_date, Changelog)

        for key, value in expected_changelog_activity.items():
            actual_value = getattr(result_changelog_activity, key, None)
            self.assertEqual(
                actual_value, value, f"Expected {key}={value}, but got {actual_value}"
            )

        for key, value in expected_changelog_join_date.items():
            actual_value = getattr(result_changelog_join_date, key, None)
            self.assertEqual(
                actual_value, value, f"Expected {key}={value}, but got {actual_value}"
            )

        self.assertIsInstance(result.new_member, Member)
        for key, value in expected_member.items():
            actual_value = getattr(result.new_member, key, None)
            self.assertEqual(
                actual_value, value, f"Expected {key}={value}, but got {actual_value}"
            )

        mock_db.commit.assert_called()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_should_wipe_ingots(self, mock_datetime) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now

        old_member = Member(
            id="123",
            discord_id="333",
            active=False,
            nickname="zezima",
            ingots=2277,
            rank=RANK.IRON,
            joined_date=now - timedelta(days=20),
            last_changed_date=now - timedelta(days=5),
        )

        expected_member = {
            "id": old_member.id,
            "discord_id": old_member.discord_id,
            "active": True,
            "nickname": old_member.nickname,
            "ingots": 0,
            "rank": old_member.rank,
            "joined_date": now,
            "last_changed_date": now,
        }

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        service = MemberService(db=mock_db)

        with patch.object(MemberService, "get_member_by_id", return_value=old_member):
            result: MemberServiceReactivateResponse = await service.reactivate_member(
                old_member.id,
                old_member.nickname,
            )

        expected_changelog_ingots = {
            "member_id": old_member.id,
            "admin_id": None,
            "change_type": ChangeType.RESET_INGOTS,
            "previous_value": 2277,
            "new_value": 0,
            "comment": "Ingots reset during reactivation",
            "timestamp": now,
        }

        result_changelog_ingots = mock_db.add.call_args_list[2][0][0]

        self.assertEqual(mock_db.add.call_count, 3)

        self.assertIsInstance(result_changelog_ingots, Changelog)

        for key, value in expected_changelog_ingots.items():
            actual_value = getattr(result_changelog_ingots, key, None)
            self.assertEqual(
                actual_value,
                value,
                f"Expected changelog {key}={value}, but got {actual_value}",
            )

        self.assertIsInstance(result.new_member, Member)
        for key, value in expected_member.items():
            actual_value = getattr(result.new_member, key, None)
            self.assertEqual(
                actual_value,
                value,
                f"Expected member {key}={value}, but got {actual_value}",
            )

        mock_db.commit.assert_called()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_should_update_nickname(
        self, mock_datetime
    ) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        old_nickname = "zezima"
        new_nickname = "muts"
        mock_datetime.now.return_value = now

        old_member = Member(
            id="123",
            discord_id="333",
            active=False,
            nickname=old_nickname,
            ingots=2277,
            rank=RANK.IRON,
            joined_date=now - timedelta(days=20),
            last_changed_date=now - timedelta(hours=1),
        )

        expected_member = {
            "id": old_member.id,
            "discord_id": old_member.discord_id,
            "active": True,
            "nickname": new_nickname,
            "ingots": old_member.ingots,
            "rank": old_member.rank,
            "joined_date": now,
            "last_changed_date": now,
        }

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        service = MemberService(db=mock_db)

        with patch.object(MemberService, "get_member_by_id", return_value=old_member):
            result: MemberServiceReactivateResponse = await service.reactivate_member(
                old_member.id, new_nickname
            )

        expected_changelog_nickname = {
            "member_id": old_member.id,
            "admin_id": None,
            "change_type": ChangeType.NAME_CHANGE,
            "previous_value": old_nickname,
            "new_value": new_nickname,
            "comment": "Nickname changed during reactivation",
            "timestamp": now,
        }

        result_changelog_nickname = mock_db.add.call_args_list[2][0][0]

        self.assertEqual(mock_db.add.call_count, 3)

        self.assertIsInstance(result_changelog_nickname, Changelog)

        for key, value in expected_changelog_nickname.items():
            actual_value = getattr(result_changelog_nickname, key, None)
            self.assertEqual(
                actual_value,
                value,
                f"Expected changelog {key}={value}, but got {actual_value}",
            )

        self.assertIsInstance(result.new_member, Member)
        for key, value in expected_member.items():
            actual_value = getattr(result.new_member, key, None)
            self.assertEqual(
                actual_value,
                value,
                f"Expected member {key}={value}, but got {actual_value}",
            )

        mock_db.commit.assert_called()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_should_update_rank(self, mock_datetime) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        old_rank = RANK.IRON
        new_rank = RANK.ADAMANT
        mock_datetime.now.return_value = now

        old_member = Member(
            id="123",
            discord_id="333",
            active=False,
            nickname="zezima",
            ingots=2277,
            rank=old_rank,
            joined_date=now - timedelta(days=20),
            last_changed_date=now - timedelta(hours=1),
        )

        expected_member = {
            "id": old_member.id,
            "discord_id": old_member.discord_id,
            "active": True,
            "nickname": old_member.nickname,
            "ingots": old_member.ingots,
            "rank": new_rank,
            "joined_date": now,
            "last_changed_date": now,
        }

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        service = MemberService(db=mock_db)

        with patch.object(MemberService, "get_member_by_id", return_value=old_member):
            result: MemberServiceReactivateResponse = await service.reactivate_member(
                old_member.id, old_member.nickname, new_rank
            )

        expected_changelog_rank = {
            "member_id": old_member.id,
            "admin_id": None,
            "change_type": ChangeType.RANK_CHANGE,
            "previous_value": old_rank,
            "new_value": new_rank,
            "comment": "Rank changed during reactivation",
            "timestamp": now,
        }

        result_changelog_rank = mock_db.add.call_args_list[2][0][0]

        self.assertEqual(mock_db.add.call_count, 3)

        self.assertIsInstance(result_changelog_rank, Changelog)

        for key, value in expected_changelog_rank.items():
            actual_value = getattr(result_changelog_rank, key, None)
            self.assertEqual(
                actual_value,
                value,
                f"Expected changelog {key}={value}, but got {actual_value}",
            )

        self.assertIsInstance(result.new_member, Member)
        for key, value in expected_member.items():
            actual_value = getattr(result.new_member, key, None)
            self.assertEqual(
                actual_value,
                value,
                f"Expected member {key}={value}, but got {actual_value}",
            )

        mock_db.commit.assert_called()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_reactivate_member_should_raise_UniqueNicknameViolation_if_Integrity_error_and_rollback(
        self, mock_datetime
    ) -> None:
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(
            side_effect=IntegrityError("nickname", None, Exception())
        )
        mock_db.rollback = AsyncMock()
        service = MemberService(db=mock_db)

        now = datetime(2025, 1, 1, 12, 0, 0)
        previous_joined_date = (now - timedelta(days=20),)
        mock_datetime.now.return_value = now

        old_member = Member(
            id="123",
            discord_id="333",
            active=False,
            nickname="zezima",
            ingots=2277,
            rank=RANK.IRON,
            joined_date=previous_joined_date,
            last_changed_date=now - timedelta(hours=1),
        )

        with patch.object(MemberService, "get_member_by_id", return_value=old_member):
            with self.assertRaises(UniqueNicknameViolation):
                _ = await service.reactivate_member(
                    old_member.id,
                    old_member.nickname,
                )

        mock_db.rollback.assert_awaited_once()

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_disable_member_should_succeed(self, mock_datetime) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now

        old_member = Member(
            id="123",
            discord_id="333",
            active=True,
            nickname="zezima",
            ingots=2277,
            rank=RANK.IRON,
            joined_date=now - timedelta(days=20),
            last_changed_date=now - timedelta(hours=1),
        )

        expected_member = {
            "id": old_member.id,
            "discord_id": old_member.discord_id,
            "active": False,
            "nickname": old_member.nickname,
            "ingots": old_member.ingots,
            "rank": old_member.rank,
            "joined_date": old_member.joined_date,
            "last_changed_date": now,
        }

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        service = MemberService(db=mock_db)

        with patch.object(MemberService, "get_member_by_id", return_value=old_member):
            result: Member = await service.disable_member(
                old_member.id,
            )

        expected_changelog_activity = {
            "member_id": old_member.id,
            "admin_id": None,
            "change_type": ChangeType.ACTIVITY_CHANGE,
            "previous_value": True,
            "new_value": False,
            "comment": "Disabled member",
            "timestamp": now,
        }

        result_changelog_activity = mock_db.add.call_args_list[0][0][0]

        self.assertEqual(mock_db.add.call_count, 1)

        self.assertIsInstance(result_changelog_activity, Changelog)

        for key, value in expected_changelog_activity.items():
            actual_value = getattr(result_changelog_activity, key, None)
            self.assertEqual(
                actual_value, value, f"Expected {key}={value}, but got {actual_value}"
            )

        self.assertIsInstance(result, Member)
        for key, value in expected_member.items():
            actual_value = getattr(result, key, None)
            self.assertEqual(
                actual_value, value, f"Expected {key}={value}, but got {actual_value}"
            )

        mock_db.commit.assert_called()

    async def test_disable_member_should_raise_MemberNotFoundException(self) -> None:
        mock_db = AsyncMock()
        service = MemberService(db=mock_db)

        with patch.object(MemberService, "get_member_by_id", return_value=None):
            with self.assertRaises(MemberNotFoundException):
                _ = await service.reactivate_member(
                    "123",
                    "bob",
                )

    @patch("ironforgedbot.services.member_service.datetime")
    async def test_disable_member_exception_should_rollback(
        self, mock_datetime
    ) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now

        old_member = Member(
            id="123",
            discord_id="333",
            active=True,
            nickname="zezima",
            ingots=2277,
            rank=RANK.IRON,
            joined_date=now - timedelta(days=20),
            last_changed_date=now - timedelta(hours=1),
        )

        expected_member = {
            "id": old_member.id,
            "discord_id": old_member.discord_id,
            "active": False,
            "nickname": old_member.nickname,
            "ingots": old_member.ingots,
            "rank": old_member.rank,
            "joined_date": old_member.joined_date,
            "last_changed_date": now,
        }

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.commit.side_effect = Exception()
        service = MemberService(db=mock_db)

        with patch.object(MemberService, "get_member_by_id", return_value=old_member):
            with self.assertRaises(Exception):
                _ = await service.disable_member(
                    old_member.id,
                )

        mock_db.rollback.assert_called()
