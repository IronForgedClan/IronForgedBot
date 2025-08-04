from datetime import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.models.changelog import ChangeType, Changelog
from ironforgedbot.models.member import Member
from ironforgedbot.services.member_service import MemberService


class TestMemberService_CreateMember(unittest.IsolatedAsyncioTestCase):
    @patch("ironforgedbot.services.member_service.datetime")
    async def test_should_create_member(self, mock_datetime) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
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

        result_member = mock_db.add.call_args_list[0][0]
        result_changelog = mock_db.add.call_args_list[1][0]

        self.assertEqual(mock_db.add.call_count, 2)

        self.assertIsInstance(result_member, Member)
        self.assertIsInstance(result_changelog, Changelog)
        for key, value in expected_changelog.items():
            actual_value = getattr(result_changelog, key, None)
            self.assertEqual(
                actual_value, value, f"Expected {key}={value}, but got {actual_value}"
            )

        expected_member["id"] = "test"
        self.assertIsInstance(result_member, Member)
        for key, value in expected_member.items():
            actual_value = getattr(result_member, key, None)
            self.assertEqual(
                actual_value, value, f"Expected {key}={value}, but got {actual_value}"
            )

        mock_db.commit.assert_called()
