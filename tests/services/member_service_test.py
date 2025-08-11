from datetime import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

from ironforgedbot.common.ranks import RANK
from ironforgedbot.models.changelog import ChangeType, Changelog
from ironforgedbot.models.member import Member
from ironforgedbot.services.member_service import (
    MemberService,
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
