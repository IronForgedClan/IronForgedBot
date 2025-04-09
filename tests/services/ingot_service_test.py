from datetime import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.models.changelog import ChangeType, Changelog
from ironforgedbot.models.member import Member
from ironforgedbot.services.ingot_service import IngotService, IngotServiceResponse


class TestIngotService(unittest.IsolatedAsyncioTestCase):
    async def test_try_add_ingots_should_fail_if_value_less_than_one(self):
        service = IngotService(db=AsyncMock())

        result = await service.try_add_ingots(123, -100, None, None)

        expected = IngotServiceResponse(False, "Quantity must be a positive value", -1)
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.ingot_service.MemberService")
    async def test_try_add_ingots_should_fail_if_member_not_found(
        self, mock_member_service
    ):
        mock_member_service_instance = MagicMock()
        mock_member_service_instance.get_member_by_discord_id = AsyncMock(
            return_value=None
        )
        mock_member_service.return_value = mock_member_service_instance
        service = IngotService(db=AsyncMock())

        result = await service.try_add_ingots(123, 100, None, None)

        expected = IngotServiceResponse(False, "Member could not be found", -1)
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.ingot_service.MemberService")
    async def test_try_add_ingots_should_fail_if_admin_id_provided_but_not_found(
        self, mock_member_service
    ):
        admin_member_discord_id = 98713

        member = Member()
        member.discord_id = 987234
        member.active = True
        member.ingots = 100

        async def get_member_side_effect(id: int):
            if id == admin_member_discord_id:
                return None
            else:
                return member

        mock_member_service_instance = MagicMock()
        mock_member_service_instance.get_member_by_discord_id = AsyncMock(
            side_effect=get_member_side_effect
        )
        mock_member_service.return_value = mock_member_service_instance

        service = IngotService(db=AsyncMock())

        result = await service.try_add_ingots(
            member.discord_id, 100, admin_member_discord_id, None
        )

        expected = IngotServiceResponse(False, "Admin member could not be found", -1)
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.ingot_service.MemberService")
    async def test_try_add_ingots_should_succeed(self, mock_member_service):
        member = Member()
        member.id = "123-fwo"
        member.discord_id = 987234
        member.active = True
        member.ingots = 100

        mock_member_service_instance = MagicMock()
        mock_member_service_instance.get_member_by_discord_id = AsyncMock(
            return_value=member
        )
        mock_member_service.return_value = mock_member_service_instance

        mock_service = AsyncMock()
        mock_service.add = MagicMock()
        service = IngotService(db=mock_service)

        result = await service.try_add_ingots(member.discord_id, 100, None, None)

        expected = IngotServiceResponse(True, "Ingots added", 200)
        mock_service.add.assert_called()
        mock_service.commit.assert_called()
        mock_service.refresh.assert_called()

        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.ingot_service.datetime")
    @patch("ironforgedbot.services.ingot_service.MemberService")
    async def test_try_add_ingots_should_create_changelog_entry(
        self, mock_member_service, mock_datetime
    ):
        now = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now

        member = Member()
        member.id = "123-fwo"
        member.discord_id = 987234
        member.active = True
        member.ingots = 100

        mock_member_service_instance = MagicMock()
        mock_member_service_instance.get_member_by_discord_id = AsyncMock(
            return_value=member
        )
        mock_member_service.return_value = mock_member_service_instance

        mock_service = AsyncMock()
        mock_service.add = MagicMock()
        service = IngotService(db=mock_service)

        result = await service.try_add_ingots(member.discord_id, 100, None, None)

        expected_result = IngotServiceResponse(True, "Ingots added", 200)
        expected_changelog = {
            "member_id": member.id,
            "admin_id": None,
            "change_type": ChangeType.ADD_INGOTS,
            "previous_value": member.ingots,
            "new_value": 200,
            "comment": "Adding ingots",
            "timestamp": now,
        }

        mock_service.add.assert_called_with(expected_changelog)
        result_changelog = mock_service.add.call_args[0][0]
        for key, value in expected_changelog.items():
            assert getattr(result_changelog, key) == value

        mock_service.commit.assert_called()
        mock_service.refresh.assert_called()
        self.assertEqual(result, expected_result)
