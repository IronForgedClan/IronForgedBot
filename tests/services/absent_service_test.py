import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.models.absent_member import AbsentMember
from ironforgedbot.models.member import Member
from ironforgedbot.services.absent_service import AbsentMemberService


class TestAbsentMemberService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_db = AsyncMock()
        self.service = AbsentMemberService(self.mock_db)

        # Mock the dependencies
        self.service.sheet = AsyncMock()
        self.service.member_service = AsyncMock()

        # Sample data for tests
        self.sample_sheet_data = [
            ["member1", "12345", "TestUser1", "2024-01-01", "On vacation", "Back soon"],
            ["member2", "67890", "TestUser2", "2024-01-02", "Medical leave", ""],
            ["", "", "", "", "", ""],  # Empty row
        ]

        self.sample_absentees = [
            AbsentMember(
                "member1", 12345, "TestUser1", "2024-01-01", "On vacation", "Back soon"
            ),
            AbsentMember(
                "member2", 67890, "TestUser2", "2024-01-02", "Medical leave", ""
            ),
            AbsentMember("", 0, "", "", "", ""),
        ]

    async def test_get_absentees_with_data(self):
        self.service.sheet.get_range.return_value = self.sample_sheet_data

        result = await self.service.get_absentees()

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].id, "member1")
        self.assertEqual(result[0].discord_id, 12345)
        self.assertEqual(result[0].nickname, "TestUser1")
        self.assertEqual(result[1].id, "member2")
        self.assertEqual(result[2].id, "")
        self.service.sheet.get_range.assert_called_once_with("AbsenceNotice", "A2:F")

    async def test_get_absentees_no_data(self):
        self.service.sheet.get_range.return_value = None

        result = await self.service.get_absentees()

        self.assertEqual(result, [])
        self.service.sheet.get_range.assert_called_once_with("AbsenceNotice", "A2:F")

    async def test_get_absentees_empty_data(self):
        self.service.sheet.get_range.return_value = []

        result = await self.service.get_absentees()

        self.assertEqual(result, [])

    async def test_get_absentees_partial_data(self):
        partial_data = [
            ["member1", "12345"],  # Missing some fields
            ["member2"],  # Missing even more fields
        ]
        self.service.sheet.get_range.return_value = partial_data

        result = await self.service.get_absentees()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, "member1")
        self.assertEqual(result[0].discord_id, 12345)
        self.assertEqual(result[0].nickname, "")
        self.assertEqual(result[1].id, "member2")
        self.assertEqual(result[1].discord_id, 0)

    async def test_get_absentees_handles_string_discord_id(self):
        data_with_string_id = [
            ["member1", "not_a_number", "TestUser1", "2024-01-01", "info", "comment"]
        ]
        self.service.sheet.get_range.return_value = data_with_string_id

        # This should raise a ValueError due to invalid int conversion
        with self.assertRaises(ValueError):
            await self.service.get_absentees()

    async def test_update_absentees_basic(self):
        absentees = self.sample_absentees[:2]  # Without empty row

        await self.service.update_absentees(absentees)

        expected_values = [
            ["member1", "12345", "TestUser1", "2024-01-01", "On vacation", "Back soon"],
            ["member2", "67890", "TestUser2", "2024-01-02", "Medical leave", ""],
        ]
        self.service.sheet.update_range.assert_called_once_with(
            "AbsenceNotice", "A2:F4", expected_values
        )

    async def test_update_absentees_with_removed_count(self):
        absentees = self.sample_absentees[:1]
        removed_count = 2

        await self.service.update_absentees(absentees, removed_count)

        expected_values = [
            ["member1", "12345", "TestUser1", "2024-01-01", "On vacation", "Back soon"],
            ["", "", "", "", "", ""],
            ["", "", "", "", "", ""],
        ]
        self.service.sheet.update_range.assert_called_once_with(
            "AbsenceNotice", "A2:F7", expected_values
        )

    async def test_update_absentees_empty_list(self):
        await self.service.update_absentees([])

        self.service.sheet.update_range.assert_called_once_with(
            "AbsenceNotice", "A2:F2", []
        )

    async def test_process_absent_members_removes_empty_entries(self):
        self.service.get_absentees = AsyncMock(
            return_value=self.sample_absentees.copy()
        )
        self.service.update_absentees = AsyncMock()

        result = await self.service.process_absent_members()

        # Should remove the empty entry
        self.assertEqual(len(result), 2)
        self.service.update_absentees.assert_called_once()
        # Check that removed_count was passed as positional argument
        call_args = self.service.update_absentees.call_args
        self.assertEqual(
            call_args[0][1], 1
        )  # removed_count is second positional argument

    async def test_process_absent_members_member_found_by_id(self):
        absentee = AbsentMember(
            "member1", 12345, "OldName", "2024-01-01", "", "comment"
        )
        mock_member = Member(
            id="member1", discord_id=12345, nickname="NewName", active=True
        )

        self.service.get_absentees = AsyncMock(return_value=[absentee])
        self.service.member_service.get_member_by_id.return_value = mock_member
        self.service.update_absentees = AsyncMock()

        result = await self.service.process_absent_members()

        self.assertEqual(result[0].nickname, "NewName")
        self.assertEqual(result[0].information, "Updated nickname.")
        self.service.member_service.get_member_by_id.assert_called_once_with("member1")

    async def test_process_absent_members_member_found_by_nickname(self):
        absentee = AbsentMember("", 0, "TestUser", "2024-01-01", "", "comment")
        mock_member = Member(
            id="member1", discord_id=12345, nickname="TestUser", active=True
        )

        self.service.get_absentees = AsyncMock(return_value=[absentee])
        self.service.member_service.get_member_by_nickname.return_value = mock_member
        self.service.update_absentees = AsyncMock()

        result = await self.service.process_absent_members()

        self.assertEqual(result[0].id, "member1")
        self.assertEqual(result[0].discord_id, 12345)
        self.service.member_service.get_member_by_nickname.assert_called_once_with(
            "TestUser"
        )

    async def test_process_absent_members_member_not_found(self):
        absentee = AbsentMember(
            "nonexistent", 0, "NonExistent", "2024-01-01", "", "comment"
        )

        self.service.get_absentees = AsyncMock(return_value=[absentee])
        self.service.member_service.get_member_by_id.return_value = None
        self.service.update_absentees = AsyncMock()

        result = await self.service.process_absent_members()

        self.assertEqual(result[0].information, "Member not found in database.")

    async def test_process_absent_members_member_inactive(self):
        absentee = AbsentMember(
            "member1", 12345, "TestUser", "2024-01-01", "", "comment"
        )
        mock_member = Member(
            id="member1", discord_id=12345, nickname="TestUser", active=False
        )

        self.service.get_absentees = AsyncMock(return_value=[absentee])
        self.service.member_service.get_member_by_id.return_value = mock_member
        self.service.update_absentees = AsyncMock()

        result = await self.service.process_absent_members()

        self.assertEqual(result[0].information, "Member has left the clan.")

    async def test_process_absent_members_updates_missing_fields(self):
        absentee = AbsentMember("", 0, "TestUser", "2024-01-01", "", "comment")
        mock_member = Member(
            id="member1", discord_id=12345, nickname="TestUser", active=True
        )

        self.service.get_absentees = AsyncMock(return_value=[absentee])
        self.service.member_service.get_member_by_nickname.return_value = mock_member
        self.service.update_absentees = AsyncMock()

        result = await self.service.process_absent_members()

        self.assertEqual(result[0].id, "member1")
        self.assertEqual(result[0].discord_id, 12345)
        self.assertEqual(result[0].nickname, "TestUser")

    async def test_process_absent_members_clears_information_when_no_updates(self):
        absentee = AbsentMember(
            "member1", 12345, "TestUser", "2024-01-01", "old info", "comment"
        )
        mock_member = Member(
            id="member1", discord_id=12345, nickname="TestUser", active=True
        )

        self.service.get_absentees = AsyncMock(return_value=[absentee])
        self.service.member_service.get_member_by_id.return_value = mock_member
        self.service.update_absentees = AsyncMock()

        result = await self.service.process_absent_members()

        self.assertEqual(result[0].information, "")

    async def test_process_absent_members_updates_short_id(self):
        absentee = AbsentMember("", 12345, "TestUser", "2024-01-01", "", "comment")
        mock_member = Member(
            id="member1", discord_id=12345, nickname="TestUser", active=True
        )

        self.service.get_absentees = AsyncMock(return_value=[absentee])
        self.service.member_service.get_member_by_nickname.return_value = mock_member
        self.service.update_absentees = AsyncMock()

        result = await self.service.process_absent_members()

        self.assertEqual(result[0].id, "member1")

    @patch("ironforgedbot.services.absent_service.Sheets")
    def test_init_creates_sheets_instance(self, mock_sheets):
        mock_db = AsyncMock()
        service = AbsentMemberService(mock_db)

        mock_sheets.assert_called_once()
        self.assertEqual(service.sheet_name, "AbsenceNotice")

    async def test_get_absentees_handles_none_values_in_entry(self):
        data_with_nones = [
            ["member1", None, "TestUser1", "2024-01-01", None, "comment"]
        ]
        self.service.sheet.get_range.return_value = data_with_nones

        result = await self.service.get_absentees()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].discord_id, 0)
        self.assertIsNone(result[0].information)

    async def test_process_absent_members_handles_iteration_during_modification(self):
        absentees_with_empties = [
            AbsentMember("", 0, "", "", "", ""),
            AbsentMember("member1", 12345, "TestUser", "2024-01-01", "", "comment"),
            AbsentMember("", 0, "", "", "", ""),
        ]

        mock_member = Member(
            id="member1", discord_id=12345, nickname="TestUser", active=True
        )

        self.service.get_absentees = AsyncMock(return_value=absentees_with_empties)
        self.service.member_service.get_member_by_id.return_value = mock_member
        self.service.update_absentees = AsyncMock()

        result = await self.service.process_absent_members()

        # Should have removed the empty entries and processed the valid one
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "member1")

        # Check that removed_count reflects the 2 removed empty entries
        call_args = self.service.update_absentees.call_args
        self.assertEqual(
            call_args[0][1], 2
        )  # removed_count is second positional argument
