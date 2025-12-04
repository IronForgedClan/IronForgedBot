import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.models.member import Member
from ironforgedbot.services.changelog_service import ChangelogService


class TestChangelogService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_db = AsyncMock()
        self.mock_db.execute = AsyncMock()
        self.mock_db.close = AsyncMock()

        self.changelog_service = ChangelogService(self.mock_db)
        self.changelog_service.member_service = AsyncMock()

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

    def test_init(self):
        service = ChangelogService(self.mock_db)
        self.assertEqual(service.db, self.mock_db)
        self.assertIsNotNone(service.member_service)

    async def test_close(self):
        await self.changelog_service.close()

        self.changelog_service.member_service.close.assert_called_once()
        self.mock_db.close.assert_called_once()

    async def test_latest_ingot_transactions_invalid_quantity_types(self):
        """Test that invalid quantity types raise TypeError."""
        invalid_values = ["three", None, 3.14, [], {}]

        for value in invalid_values:
            with self.subTest(input=value):
                with self.assertRaises(TypeError) as context:
                    await self.changelog_service.latest_ingot_transactions(12345, value)
                self.assertEqual(
                    str(context.exception), "Quantity must be a valid integer"
                )

    async def test_latest_ingot_transactions_invalid_quantity_values(self):
        """Test that invalid quantity values return empty list."""
        invalid_values = [0, -1, -100]

        for value in invalid_values:
            with self.subTest(input=value):
                result = await self.changelog_service.latest_ingot_transactions(
                    12345, value
                )
                self.assertEqual(result, [])

    async def test_latest_ingot_transactions_empty_result(self):
        """Test when no transactions exist for a member."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        result = await self.changelog_service.latest_ingot_transactions(12345, 5)

        self.assertEqual(result, [])
        self.mock_db.execute.assert_called_once()

    async def test_latest_ingot_transactions_single_transaction(self):
        """Test with a single transaction."""
        changelog_entry = Changelog(
            id=1,
            member_id="test-member-id",
            admin_id=None,
            change_type=ChangeType.ADD_INGOTS,
            previous_value="1000",
            new_value="1500",
            comment="Adding ingots",
            timestamp=self.fixed_datetime,
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [changelog_entry]
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        result = await self.changelog_service.latest_ingot_transactions(12345, 5)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].change_type, ChangeType.ADD_INGOTS)
        self.assertEqual(result[0].previous_value, "1000")
        self.assertEqual(result[0].new_value, "1500")
        self.assertEqual(result[0].comment, "Adding ingots")

    async def test_latest_ingot_transactions_multiple_transactions(self):
        """Test with multiple transactions."""
        changelog_entries = [
            Changelog(
                id=3,
                member_id="test-member-id",
                admin_id="admin-id",
                change_type=ChangeType.ADD_INGOTS,
                previous_value="1000",
                new_value="1200",
                comment="Adding ingots",
                timestamp=datetime(2025, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
            ),
            Changelog(
                id=2,
                member_id="test-member-id",
                admin_id="admin-id",
                change_type=ChangeType.REMOVE_INGOTS,
                previous_value="1200",
                new_value="1100",
                comment="Purchase raffle tickets",
                timestamp=datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            ),
            Changelog(
                id=1,
                member_id="test-member-id",
                admin_id=None,
                change_type=ChangeType.ADD_INGOTS,
                previous_value="1000",
                new_value="1100",
                comment="Adding ingots",
                timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = changelog_entries
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        result = await self.changelog_service.latest_ingot_transactions(12345, 5)

        self.assertEqual(len(result), 3)

        # Verify they're in descending order by timestamp (most recent first)
        self.assertEqual(result[0].id, 3)
        self.assertEqual(result[1].id, 2)
        self.assertEqual(result[2].id, 1)

    async def test_latest_ingot_transactions_respects_quantity_limit(self):
        """Test that quantity parameter limits results."""
        changelog_entries = [
            Changelog(
                id=i,
                member_id=f"123-{i}",
                admin_id=None,
                change_type=ChangeType.ADD_INGOTS,
                previous_value="1000",
                new_value="1100",
                comment=f"Transaction {i}",
                timestamp=datetime(2025, 1, i, 12, 0, 0, tzinfo=timezone.utc),
            )
            for i in range(1, 6)
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = changelog_entries
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        result = await self.changelog_service.latest_ingot_transactions(12345, 5)

        self.assertEqual(len(result), 5)

    async def test_latest_ingot_transactions_only_ingot_types(self):
        """Test that the query filters for only ADD_INGOTS and REMOVE_INGOTS types."""
        changelog_entries = [
            Changelog(
                id=1,
                member_id="test-member-id",
                admin_id=None,
                change_type=ChangeType.ADD_INGOTS,
                previous_value="1000",
                new_value="1100",
                comment="Adding ingots",
                timestamp=self.fixed_datetime,
            ),
            Changelog(
                id=2,
                member_id="test-member-id",
                admin_id=None,
                change_type=ChangeType.REMOVE_INGOTS,
                previous_value="1100",
                new_value="1000",
                comment="Removing ingots",
                timestamp=self.fixed_datetime,
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = changelog_entries
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        result = await self.changelog_service.latest_ingot_transactions(12345, 5)

        self.mock_db.execute.assert_called_once()

        query = self.mock_db.execute.call_args[0][0]

        query_str = str(query)
        self.assertIn("changelog.change_type", query_str.lower())

        self.assertEqual(len(result), 2)
        for entry in result:
            self.assertIn(
                entry.change_type, [ChangeType.ADD_INGOTS, ChangeType.REMOVE_INGOTS]
            )

    async def test_latest_ingot_transactions_with_none_values(self):
        """Test handling of None values in previous_value and new_value."""
        changelog_entry = Changelog(
            id=1,
            member_id="test-member-id",
            admin_id=None,
            change_type=ChangeType.ADD_INGOTS,
            previous_value=None,
            new_value="100",
            comment="Initial ingots",
            timestamp=self.fixed_datetime,
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [changelog_entry]
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        result = await self.changelog_service.latest_ingot_transactions(12345, 5)

        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0].previous_value)
        self.assertEqual(result[0].new_value, "100")

    async def test_latest_ingot_transactions_large_quantity(self):
        """Test with a very large quantity parameter."""
        changelog_entries = [
            Changelog(
                id=1,
                member_id="test-member-id",
                admin_id=None,
                change_type=ChangeType.ADD_INGOTS,
                previous_value="0",
                new_value="100",
                comment="Adding ingots",
                timestamp=self.fixed_datetime,
            )
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = changelog_entries
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        result = await self.changelog_service.latest_ingot_transactions(12345, 1000)

        self.assertEqual(len(result), 1)

    async def test_latest_ingot_transactions_verify_query_called(self):
        """Test that database execute is called with proper query."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        await self.changelog_service.latest_ingot_transactions(12345, 5)

        self.mock_db.execute.assert_called_once()

        call_args = self.mock_db.execute.call_args
        self.assertIsNotNone(call_args)

    async def test_latest_ingot_transactions_mixed_change_types(self):
        """Test with a mix of ADD and REMOVE transactions."""
        changelog_entries = [
            Changelog(
                id=1,
                member_id="test-member-id",
                admin_id=None,
                change_type=ChangeType.ADD_INGOTS,
                previous_value="0",
                new_value="100",
                comment="Adding ingots",
                timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            ),
            Changelog(
                id=2,
                member_id="test-member-id",
                admin_id=None,
                change_type=ChangeType.REMOVE_INGOTS,
                previous_value="100",
                new_value="50",
                comment="Purchase raffle tickets",
                timestamp=datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            ),
            Changelog(
                id=3,
                member_id="test-member-id",
                admin_id=None,
                change_type=ChangeType.ADD_INGOTS,
                previous_value="50",
                new_value="150",
                comment="Adding ingots",
                timestamp=datetime(2025, 1, 3, 12, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = changelog_entries
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        result = await self.changelog_service.latest_ingot_transactions(12345, 5)

        self.assertEqual(len(result), 3)

        change_types = [entry.change_type for entry in result]
        self.assertIn(ChangeType.ADD_INGOTS, change_types)
        self.assertIn(ChangeType.REMOVE_INGOTS, change_types)

    async def test_latest_ingot_transactions_quantity_one(self):
        """Test with quantity parameter of 1."""
        changelog_entry = Changelog(
            id=1,
            member_id="test-member-id",
            admin_id=None,
            change_type=ChangeType.ADD_INGOTS,
            previous_value="0",
            new_value="100",
            comment="Adding ingots",
            timestamp=self.fixed_datetime,
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [changelog_entry]
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result

        result = await self.changelog_service.latest_ingot_transactions(12345, 1)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 1)
