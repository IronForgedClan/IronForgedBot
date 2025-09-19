import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.models.member import Member
from ironforgedbot.services.ingot_service import IngotService, IngotServiceResponse


class TestIngotService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_db = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()
        self.mock_db.close = AsyncMock()
        
        self.ingot_service = IngotService(self.mock_db)
        self.ingot_service.member_service = AsyncMock()
        
        self.fixed_datetime = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        self.sample_member = Member(
            id="test-member-id",
            discord_id=12345,
            active=True,
            nickname="TestUser",
            ingots=1000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )
        
        self.admin_member = Member(
            id="admin-member-id",
            discord_id=67890,
            active=True,
            nickname="AdminUser",
            ingots=5000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )
        
        self.poor_member = Member(
            id="poor-member-id",
            discord_id=11111,
            active=True,
            nickname="PoorUser",
            ingots=50,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )

    def test_init(self):
        service = IngotService(self.mock_db)
        self.assertEqual(service.db, self.mock_db)
        self.assertIsNotNone(service.member_service)

    async def test_close(self):
        await self.ingot_service.close()
        
        self.ingot_service.member_service.close.assert_called_once()
        self.mock_db.close.assert_called_once()


    async def test_try_add_ingots_invalid_quantity_types(self):
        invalid_values = ["three", None, 3.14, [], {}]
        
        for value in invalid_values:
            with self.subTest(input=value):
                with self.assertRaises(TypeError) as context:
                    await self.ingot_service.try_add_ingots(12345, value, None, None)
                self.assertEqual(str(context.exception), "Quantity must be a valid integer")

    async def test_try_add_ingots_invalid_quantity_values(self):
        invalid_values = [0, -1, -100]
        
        for value in invalid_values:
            with self.subTest(input=value):
                result = await self.ingot_service.try_add_ingots(12345, value, None, None)
                expected = IngotServiceResponse(False, "Quantity must be a positive value", -1)
                self.assertEqual(result, expected)

    async def test_try_add_ingots_member_not_found(self):
        self.ingot_service.member_service.get_member_by_discord_id.return_value = None
        
        result = await self.ingot_service.try_add_ingots(99999, 100, None, None)
        
        expected = IngotServiceResponse(False, "Member could not be found", -1)
        self.assertEqual(result, expected)
        self.ingot_service.member_service.get_member_by_discord_id.assert_called_once_with(99999)

    async def test_try_add_ingots_admin_not_found(self):
        async def get_member_side_effect(discord_id: int):
            if discord_id == 12345:
                return self.sample_member
            else:
                return None
        
        self.ingot_service.member_service.get_member_by_discord_id.side_effect = get_member_side_effect
        
        result = await self.ingot_service.try_add_ingots(12345, 100, 99999, None)
        
        expected = IngotServiceResponse(False, "Admin member could not be found", -1)
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_try_add_ingots_success_basic(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.ingot_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        result = await self.ingot_service.try_add_ingots(12345, 500, None, None)
        
        expected = IngotServiceResponse(True, "Ingots added", 1500)
        self.assertEqual(result, expected)
        self.assertEqual(self.sample_member.ingots, 1500)
        self.assertEqual(self.sample_member.last_changed_date, self.fixed_datetime)
        
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once_with(self.sample_member)

    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_try_add_ingots_success_with_admin(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        async def get_member_side_effect(discord_id: int):
            if discord_id == 12345:
                return self.sample_member
            elif discord_id == 67890:
                return self.admin_member
            return None
        
        self.ingot_service.member_service.get_member_by_discord_id.side_effect = get_member_side_effect
        
        result = await self.ingot_service.try_add_ingots(12345, 250, 67890, "Test reason")
        
        expected = IngotServiceResponse(True, "Ingots added", 1250)
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_try_add_ingots_creates_correct_changelog(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.ingot_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        await self.ingot_service.try_add_ingots(12345, 300, None, "Test add reason")
        
        self.mock_db.add.assert_called_once()
        changelog_entry = self.mock_db.add.call_args[0][0]
        
        self.assertIsInstance(changelog_entry, Changelog)
        self.assertEqual(changelog_entry.member_id, "test-member-id")
        self.assertIsNone(changelog_entry.admin_id)
        self.assertEqual(changelog_entry.change_type, ChangeType.ADD_INGOTS)
        self.assertEqual(changelog_entry.previous_value, 1000)
        self.assertEqual(changelog_entry.new_value, 1300)
        self.assertEqual(changelog_entry.comment, "Test add reason")
        self.assertEqual(changelog_entry.timestamp, self.fixed_datetime)

    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_try_add_ingots_default_comment(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.ingot_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        await self.ingot_service.try_add_ingots(12345, 100, None, None)
        
        changelog_entry = self.mock_db.add.call_args[0][0]
        self.assertEqual(changelog_entry.comment, "Adding ingots")

    async def test_try_add_ingots_large_quantities(self):
        large_values = [1, 100, 100_000, 999_999_999]
        
        for value in large_values:
            with self.subTest(input=value):
                test_member = Member(
                    id="test-id",
                    discord_id=12345,
                    active=True,
                    nickname="TestUser",
                    ingots=1000,
                    joined_date=self.fixed_datetime,
                    last_changed_date=self.fixed_datetime,
                )
                
                self.ingot_service.member_service.get_member_by_discord_id.return_value = test_member
                
                result = await self.ingot_service.try_add_ingots(12345, value, None, None)
                
                expected = IngotServiceResponse(True, "Ingots added", 1000 + value)
                self.assertEqual(result, expected)


    async def test_try_remove_ingots_invalid_quantity_types(self):
        invalid_values = ["three", None, 3.14, [], {}]
        
        for value in invalid_values:
            with self.subTest(input=value):
                with self.assertRaises(TypeError) as context:
                    await self.ingot_service.try_remove_ingots(12345, value, None, None)
                self.assertEqual(str(context.exception), "Quantity must be a valid integer")

    async def test_try_remove_ingots_invalid_quantity_values(self):
        invalid_values = [100, 10, 1, 0]
        
        for value in invalid_values:
            with self.subTest(input=value):
                result = await self.ingot_service.try_remove_ingots(12345, value, None, None)
                expected = IngotServiceResponse(False, "Quantity must be a negative value", -1)
                self.assertEqual(result, expected)

    async def test_try_remove_ingots_member_not_found(self):
        self.ingot_service.member_service.get_member_by_discord_id.return_value = None
        
        result = await self.ingot_service.try_remove_ingots(99999, -100, None, None)
        
        expected = IngotServiceResponse(False, "Member could not be found", -1)
        self.assertEqual(result, expected)

    async def test_try_remove_ingots_admin_not_found(self):
        async def get_member_side_effect(discord_id: int):
            if discord_id == 12345:
                return self.sample_member
            else:
                return None
        
        self.ingot_service.member_service.get_member_by_discord_id.side_effect = get_member_side_effect
        
        result = await self.ingot_service.try_remove_ingots(12345, -100, 99999, None)
        
        expected = IngotServiceResponse(False, "Admin member could not be found", -1)
        self.assertEqual(result, expected)

    async def test_try_remove_ingots_insufficient_funds(self):
        self.ingot_service.member_service.get_member_by_discord_id.return_value = self.poor_member
        
        result = await self.ingot_service.try_remove_ingots(11111, -100, None, None)
        
        expected = IngotServiceResponse(
            False, 
            "Member does not have enough ingots to remove that amount", 
            50
        )
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_try_remove_ingots_success_basic(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.ingot_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        result = await self.ingot_service.try_remove_ingots(12345, -300, None, None)
        
        expected = IngotServiceResponse(True, "Ingots removed", 700)
        self.assertEqual(result, expected)
        self.assertEqual(self.sample_member.ingots, 700)
        self.assertEqual(self.sample_member.last_changed_date, self.fixed_datetime)
        
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once_with(self.sample_member)

    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_try_remove_ingots_success_with_admin(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        async def get_member_side_effect(discord_id: int):
            if discord_id == 12345:
                return self.sample_member
            elif discord_id == 67890:
                return self.admin_member
            return None
        
        self.ingot_service.member_service.get_member_by_discord_id.side_effect = get_member_side_effect
        
        result = await self.ingot_service.try_remove_ingots(12345, -250, 67890, "Test removal")
        
        expected = IngotServiceResponse(True, "Ingots removed", 750)
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_try_remove_ingots_creates_correct_changelog(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.ingot_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        await self.ingot_service.try_remove_ingots(12345, -200, None, "Test remove reason")
        
        self.mock_db.add.assert_called_once()
        changelog_entry = self.mock_db.add.call_args[0][0]
        
        self.assertIsInstance(changelog_entry, Changelog)
        self.assertEqual(changelog_entry.member_id, "test-member-id")
        self.assertIsNone(changelog_entry.admin_id)
        self.assertEqual(changelog_entry.change_type, ChangeType.REMOVE_INGOTS)
        self.assertEqual(changelog_entry.previous_value, 1000)
        self.assertEqual(changelog_entry.new_value, 800)
        self.assertEqual(changelog_entry.comment, "Test remove reason")
        self.assertEqual(changelog_entry.timestamp, self.fixed_datetime)

    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_try_remove_ingots_default_comment(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        self.ingot_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        await self.ingot_service.try_remove_ingots(12345, -100, None, None)
        
        changelog_entry = self.mock_db.add.call_args[0][0]
        self.assertEqual(changelog_entry.comment, "Removing ingots")

    async def test_try_remove_ingots_large_quantities(self):
        large_values = [-1, -100, -100_000]
        
        for value in large_values:
            with self.subTest(input=value):
                rich_member = Member(
                    id="rich-id",
                    discord_id=12345,
                    active=True,
                    nickname="RichUser",
                    ingots=1_000_000,
                    joined_date=self.fixed_datetime,
                    last_changed_date=self.fixed_datetime,
                )
                
                self.ingot_service.member_service.get_member_by_discord_id.return_value = rich_member
                
                result = await self.ingot_service.try_remove_ingots(12345, value, None, None)
                
                expected = IngotServiceResponse(True, "Ingots removed", 1_000_000 + value)
                self.assertEqual(result, expected)

    async def test_try_remove_ingots_exact_balance(self):
        self.ingot_service.member_service.get_member_by_discord_id.return_value = self.poor_member
        
        result = await self.ingot_service.try_remove_ingots(11111, -50, None, None)
        
        expected = IngotServiceResponse(True, "Ingots removed", 0)
        self.assertEqual(result, expected)

    async def test_try_remove_ingots_one_more_than_balance(self):
        self.ingot_service.member_service.get_member_by_discord_id.return_value = self.poor_member
        
        result = await self.ingot_service.try_remove_ingots(11111, -51, None, None)
        
        expected = IngotServiceResponse(
            False, 
            "Member does not have enough ingots to remove that amount", 
            50
        )
        self.assertEqual(result, expected)


    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_add_remove_sequence(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        test_member = Member(
            id="test-id",
            discord_id=12345,
            active=True,
            nickname="TestUser",
            ingots=1000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )
        
        self.ingot_service.member_service.get_member_by_discord_id.return_value = test_member
        
        result1 = await self.ingot_service.try_add_ingots(12345, 500, None, None)
        self.assertEqual(result1.new_total, 1500)
        
        result2 = await self.ingot_service.try_remove_ingots(12345, -300, None, None)
        self.assertEqual(result2.new_total, 1200)
        
        result3 = await self.ingot_service.try_remove_ingots(12345, -1300, None, None)
        self.assertFalse(result3.status)
        self.assertEqual(result3.new_total, 1200)

    async def test_zero_ingot_member_operations(self):
        zero_member = Member(
            id="zero-id",
            discord_id=12345,
            active=True,
            nickname="ZeroUser",
            ingots=0,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )
        
        self.ingot_service.member_service.get_member_by_discord_id.return_value = zero_member
        
        result1 = await self.ingot_service.try_add_ingots(12345, 100, None, None)
        self.assertTrue(result1.status)
        self.assertEqual(result1.new_total, 100)
        
        zero_member.ingots = 0
        
        result2 = await self.ingot_service.try_remove_ingots(12345, -1, None, None)
        self.assertFalse(result2.status)
        self.assertEqual(result2.new_total, 0)

    @patch("ironforgedbot.services.ingot_service.datetime")
    async def test_admin_id_stored_correctly(self, mock_datetime):
        mock_datetime.now.return_value = self.fixed_datetime
        
        async def get_member_side_effect(discord_id: int):
            if discord_id == 12345:
                return self.sample_member
            elif discord_id == 67890:
                return self.admin_member
            return None
        
        self.ingot_service.member_service.get_member_by_discord_id.side_effect = get_member_side_effect
        
        await self.ingot_service.try_add_ingots(12345, 100, 67890, "Admin action")
        
        changelog_entry = self.mock_db.add.call_args[0][0]
        self.assertEqual(changelog_entry.admin_id, "admin-member-id")