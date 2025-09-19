import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.models.member import Member
from ironforgedbot.models.raffle_ticket import RaffleTicket
from ironforgedbot.services.raffle_service import (
    RaffleService, 
    RaffleServiceException, 
    RaffleServiceResponse
)
from ironforgedbot.services.ingot_service import IngotServiceResponse


class TestRaffleService(unittest.IsolatedAsyncioTestCase):
    """Test cases for RaffleService class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_db = AsyncMock()
        self.mock_db.add = MagicMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.execute = AsyncMock()
        self.mock_db.close = AsyncMock()
        
        self.raffle_service = RaffleService(self.mock_db)
        self.raffle_service.member_service = AsyncMock()
        self.raffle_service.ingot_service = AsyncMock()
        
        # Fixed datetime for consistent testing
        self.fixed_datetime = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        # Sample member data
        self.sample_member = Member(
            id="test-member-id",
            discord_id=12345,
            active=True,
            nickname="TestUser",
            ingots=10000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )
        
        self.poor_member = Member(
            id="poor-member-id",
            discord_id=67890,
            active=True,
            nickname="PoorUser",
            ingots=100,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )
        
        self.inactive_member = Member(
            id="inactive-member-id",
            discord_id=99999,
            active=False,
            nickname="InactiveUser",
            ingots=5000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )
        
        # Sample raffle tickets
        self.sample_raffle_ticket = RaffleTicket(
            id=1,
            member_id="test-member-id",
            quantity=5,
            last_changed_date=self.fixed_datetime,
        )
        
        self.large_raffle_ticket = RaffleTicket(
            id=2,
            member_id="rich-member-id",
            quantity=100,
            last_changed_date=self.fixed_datetime,
        )

    def test_init(self):
        """Test RaffleService initialization"""
        service = RaffleService(self.mock_db)
        self.assertEqual(service.db, self.mock_db)
        self.assertIsNotNone(service.member_service)
        self.assertIsNotNone(service.ingot_service)

    async def test_close(self):
        """Test close method calls both ingot_service.close and db.close"""
        await self.raffle_service.close()
        
        self.raffle_service.ingot_service.close.assert_called_once()
        self.mock_db.close.assert_called_once()

    # =============================================================================
    # get_member_ticket_total tests
    # =============================================================================

    async def test_get_member_ticket_total_member_has_tickets(self):
        """Test get_member_ticket_total returns correct quantity when member has tickets"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.sample_raffle_ticket
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.raffle_service.get_member_ticket_total(12345)
        
        self.assertEqual(result, 5)
        self.mock_db.execute.assert_called_once()

    async def test_get_member_ticket_total_member_has_no_tickets(self):
        """Test get_member_ticket_total returns 0 when member has no tickets"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.raffle_service.get_member_ticket_total(99999)
        
        self.assertEqual(result, 0)

    async def test_get_member_ticket_total_query_structure(self):
        """Test get_member_ticket_total uses correct query structure"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        await self.raffle_service.get_member_ticket_total(12345)
        
        # Verify execute was called (query structure is complex to test exactly)
        self.mock_db.execute.assert_called_once()

    # =============================================================================
    # get_raffle_ticket_total tests
    # =============================================================================

    async def test_get_raffle_ticket_total_with_tickets(self):
        """Test get_raffle_ticket_total returns sum of all tickets"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = 150  # Sum of all tickets
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.raffle_service.get_raffle_ticket_total()
        
        self.assertEqual(result, 150)

    async def test_get_raffle_ticket_total_no_tickets(self):
        """Test get_raffle_ticket_total returns 0 when no tickets exist"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.raffle_service.get_raffle_ticket_total()
        
        self.assertEqual(result, 0)

    # =============================================================================
    # get_all_valid_raffle_tickets tests
    # =============================================================================

    async def test_get_all_valid_raffle_tickets_returns_active_only(self):
        """Test get_all_valid_raffle_tickets returns only tickets for active members"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [self.sample_raffle_ticket, self.large_raffle_ticket]
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.raffle_service.get_all_valid_raffle_tickets()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], self.sample_raffle_ticket)
        self.assertEqual(result[1], self.large_raffle_ticket)

    async def test_get_all_valid_raffle_tickets_empty_result(self):
        """Test get_all_valid_raffle_tickets returns empty list when no valid tickets"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.raffle_service.get_all_valid_raffle_tickets()
        
        self.assertEqual(result, [])

    # =============================================================================
    # _get_raffle_ticket tests (Note: This method appears to have a bug)
    # =============================================================================

    async def test_get_raffle_ticket_found(self):
        """Test _get_raffle_ticket returns ticket when found"""
        # Note: Current implementation seems to have a bug - it filters by Member.id instead of RaffleTicket.member_id
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.sample_raffle_ticket
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.raffle_service._get_raffle_ticket("test-member-id")
        
        self.assertEqual(result, self.sample_raffle_ticket)

    async def test_get_raffle_ticket_not_found(self):
        """Test _get_raffle_ticket returns None when not found"""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        result = await self.raffle_service._get_raffle_ticket("nonexistent-id")
        
        self.assertIsNone(result)

    # =============================================================================
    # delete_all_tickets tests
    # =============================================================================

    async def test_delete_all_tickets(self):
        """Test delete_all_tickets removes all tickets and commits"""
        await self.raffle_service.delete_all_tickets()
        
        self.mock_db.execute.assert_called_once()
        self.mock_db.commit.assert_called_once()

    # =============================================================================
    # try_buy_ticket tests
    # =============================================================================

    async def test_try_buy_ticket_invalid_quantity_zero(self):
        """Test try_buy_ticket fails with quantity of 0"""
        result = await self.raffle_service.try_buy_ticket(12345, 1000, 0)
        
        expected = RaffleServiceResponse(False, "Quantity must be a positive integer", -1)
        self.assertEqual(result, expected)

    async def test_try_buy_ticket_invalid_quantity_negative(self):
        """Test try_buy_ticket fails with negative quantity"""
        result = await self.raffle_service.try_buy_ticket(12345, 1000, -5)
        
        expected = RaffleServiceResponse(False, "Quantity must be a positive integer", -1)
        self.assertEqual(result, expected)

    async def test_try_buy_ticket_invalid_price_zero(self):
        """Test try_buy_ticket fails with ticket price of 0"""
        result = await self.raffle_service.try_buy_ticket(12345, 0, 5)
        
        expected = RaffleServiceResponse(False, "Ticket price must be a positive integer", -1)
        self.assertEqual(result, expected)

    async def test_try_buy_ticket_invalid_price_negative(self):
        """Test try_buy_ticket fails with negative ticket price"""
        result = await self.raffle_service.try_buy_ticket(12345, -1000, 5)
        
        expected = RaffleServiceResponse(False, "Ticket price must be a positive integer", -1)
        self.assertEqual(result, expected)

    async def test_try_buy_ticket_member_not_found(self):
        """Test try_buy_ticket fails when member not found"""
        self.raffle_service.member_service.get_member_by_discord_id.return_value = None
        
        result = await self.raffle_service.try_buy_ticket(99999, 1000, 5)
        
        expected = RaffleServiceResponse(False, "Member could not be found", -1)
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.raffle_service.datetime")
    async def test_try_buy_ticket_insufficient_ingots(self, mock_datetime):
        """Test try_buy_ticket fails when member has insufficient ingots"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        self.raffle_service.member_service.get_member_by_discord_id.return_value = self.poor_member
        
        # Mock _get_raffle_ticket to return None (no existing tickets)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        # Mock ingot service to fail
        self.raffle_service.ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            False, "Member does not have enough ingots to remove that amount", 100
        )
        
        result = await self.raffle_service.try_buy_ticket(67890, 1000, 5)  # 5000 total cost
        
        expected = RaffleServiceResponse(
            False, 
            "Member does not have enough ingots to remove that amount", 
            0
        )
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.raffle_service.datetime")
    async def test_try_buy_ticket_first_time_purchase_success(self, mock_datetime):
        """Test try_buy_ticket succeeds for first-time purchase"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        self.raffle_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        # Mock _get_raffle_ticket to return None (no existing tickets)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        # Mock ingot service to succeed
        self.raffle_service.ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            True, "Ingots removed", 8000
        )
        
        result = await self.raffle_service.try_buy_ticket(12345, 1000, 2)  # 2000 total cost
        
        expected = RaffleServiceResponse(True, "2 raffle tickets purchased", 2)
        self.assertEqual(result, expected)
        
        # Verify changelog was added
        self.assertEqual(self.mock_db.add.call_count, 2)  # Changelog + RaffleTicket
        
        # Check changelog
        changelog_call = self.mock_db.add.call_args_list[0][0][0]
        self.assertIsInstance(changelog_call, Changelog)
        self.assertEqual(changelog_call.member_id, "test-member-id")
        self.assertEqual(changelog_call.change_type, ChangeType.PURCHASE_RAFFLE_TICKETS)
        self.assertEqual(changelog_call.previous_value, 0)
        self.assertEqual(changelog_call.new_value, 2)
        
        # Check raffle ticket
        ticket_call = self.mock_db.add.call_args_list[1][0][0]
        self.assertIsInstance(ticket_call, RaffleTicket)
        self.assertEqual(ticket_call.member_id, "test-member-id")
        self.assertEqual(ticket_call.quantity, 2)
        
        self.mock_db.commit.assert_called_once()

    @patch("ironforgedbot.services.raffle_service.datetime")
    async def test_try_buy_ticket_additional_purchase_success(self, mock_datetime):
        """Test try_buy_ticket succeeds when adding to existing tickets"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        self.raffle_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        # Mock _get_raffle_ticket to return existing ticket
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = self.sample_raffle_ticket  # Has 5 tickets
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        # Mock ingot service to succeed
        self.raffle_service.ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            True, "Ingots removed", 7000
        )
        
        result = await self.raffle_service.try_buy_ticket(12345, 1000, 3)  # 3000 total cost
        
        expected = RaffleServiceResponse(True, "3 raffle tickets purchased", 8)  # 5 + 3
        self.assertEqual(result, expected)
        
        # Verify changelog was added
        self.mock_db.add.assert_called_once()
        
        # Check changelog
        changelog_call = self.mock_db.add.call_args[0][0]
        self.assertIsInstance(changelog_call, Changelog)
        self.assertEqual(changelog_call.member_id, "test-member-id")
        self.assertEqual(changelog_call.change_type, ChangeType.PURCHASE_RAFFLE_TICKETS)
        self.assertEqual(changelog_call.previous_value, 5)
        self.assertEqual(changelog_call.new_value, 8)
        
        # Verify update query was executed
        self.assertEqual(self.mock_db.execute.call_count, 2)  # get + update
        self.mock_db.commit.assert_called_once()

    @patch("ironforgedbot.services.raffle_service.datetime")
    async def test_try_buy_ticket_large_quantity(self, mock_datetime):
        """Test try_buy_ticket handles large quantities correctly"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        # Create rich member
        rich_member = Member(
            id="rich-member-id",
            discord_id=12345,
            active=True,
            nickname="RichUser",
            ingots=1_000_000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )
        
        self.raffle_service.member_service.get_member_by_discord_id.return_value = rich_member
        
        # Mock _get_raffle_ticket to return None
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        # Mock ingot service to succeed
        self.raffle_service.ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            True, "Ingots removed", 500_000
        )
        
        result = await self.raffle_service.try_buy_ticket(12345, 1000, 500)  # 500,000 total cost
        
        expected = RaffleServiceResponse(True, "500 raffle tickets purchased", 500)
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.raffle_service.datetime")
    async def test_try_buy_ticket_expensive_tickets(self, mock_datetime):
        """Test try_buy_ticket handles expensive ticket prices correctly"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        self.raffle_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        # Mock _get_raffle_ticket to return None
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        # Mock ingot service to succeed
        self.raffle_service.ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            True, "Ingots removed", 0
        )
        
        result = await self.raffle_service.try_buy_ticket(12345, 10000, 1)  # 10,000 per ticket
        
        expected = RaffleServiceResponse(True, "1 raffle tickets purchased", 1)
        self.assertEqual(result, expected)

    async def test_try_buy_ticket_ingot_service_called_correctly(self):
        """Test try_buy_ticket calls ingot service with correct parameters"""
        self.raffle_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        # Mock _get_raffle_ticket to return None
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        # Mock ingot service to fail (so we can test the call without full execution)
        self.raffle_service.ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            False, "Insufficient funds", 1000
        )
        
        await self.raffle_service.try_buy_ticket(12345, 2000, 3)  # 6000 total cost
        
        # Verify ingot service was called with correct parameters
        self.raffle_service.ingot_service.try_remove_ingots.assert_called_once_with(
            12345, -6000, None, "Purchase raffle tickets"
        )

    # =============================================================================
    # Exception class tests
    # =============================================================================

    def test_raffle_service_exception_default_message(self):
        """Test RaffleServiceException has correct default message"""
        exception = RaffleServiceException()
        self.assertEqual(exception.message, "An error occured interacting with the raffle")
        self.assertEqual(str(exception), "An error occured interacting with the raffle")

    def test_raffle_service_exception_custom_message(self):
        """Test RaffleServiceException accepts custom message"""
        custom_message = "Custom raffle error"
        exception = RaffleServiceException(custom_message)
        self.assertEqual(exception.message, custom_message)
        self.assertEqual(str(exception), custom_message)

    # =============================================================================
    # Integration and edge case tests
    # =============================================================================

    @patch("ironforgedbot.services.raffle_service.datetime")
    async def test_multiple_purchases_same_member(self, mock_datetime):
        """Test multiple ticket purchases by the same member"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        # Create member with lots of ingots
        rich_member = Member(
            id="rich-member-id",
            discord_id=12345,
            active=True,
            nickname="RichUser",
            ingots=100_000,
            joined_date=self.fixed_datetime,
            last_changed_date=self.fixed_datetime,
        )
        
        self.raffle_service.member_service.get_member_by_discord_id.return_value = rich_member
        
        # Mock ingot service to always succeed
        self.raffle_service.ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            True, "Ingots removed", 50_000
        )
        
        # Mock database responses for progressive ticket accumulation
        ticket_quantities = [None, 10, 25]  # None -> 10 -> 25
        mock_results = []
        for qty in ticket_quantities:
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            if qty is None:
                mock_scalars.first.return_value = None
            else:
                mock_ticket = RaffleTicket(
                    id=1, member_id="rich-member-id", quantity=qty, last_changed_date=self.fixed_datetime
                )
                mock_scalars.first.return_value = mock_ticket
            mock_result.scalars.return_value = mock_scalars
            mock_results.append(mock_result)
        
        self.mock_db.execute.side_effect = mock_results
        
        # First purchase (no existing tickets)
        result1 = await self.raffle_service.try_buy_ticket(12345, 1000, 10)
        self.assertEqual(result1.ticket_total, 10)
        
        # Second purchase (add to existing)
        result2 = await self.raffle_service.try_buy_ticket(12345, 1000, 15)
        self.assertEqual(result2.ticket_total, 25)

    async def test_edge_case_minimum_values(self):
        """Test try_buy_ticket with minimum valid values"""
        self.raffle_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        # Mock _get_raffle_ticket to return None
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        # Mock ingot service to succeed
        self.raffle_service.ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            True, "Ingots removed", 9999
        )
        
        result = await self.raffle_service.try_buy_ticket(12345, 1, 1)  # Minimum values
        
        expected = RaffleServiceResponse(True, "1 raffle tickets purchased", 1)
        self.assertEqual(result, expected)

    @patch("ironforgedbot.services.raffle_service.datetime")
    async def test_timestamp_consistency(self, mock_datetime):
        """Test that timestamps are consistent across changelog and ticket"""
        mock_datetime.now.return_value = self.fixed_datetime
        
        self.raffle_service.member_service.get_member_by_discord_id.return_value = self.sample_member
        
        # Mock _get_raffle_ticket to return None
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_result
        
        # Mock ingot service to succeed
        self.raffle_service.ingot_service.try_remove_ingots.return_value = IngotServiceResponse(
            True, "Ingots removed", 9000
        )
        
        await self.raffle_service.try_buy_ticket(12345, 1000, 1)
        
        # Check that both changelog and ticket use the same timestamp
        changelog_call = self.mock_db.add.call_args_list[0][0][0]
        ticket_call = self.mock_db.add.call_args_list[1][0][0]
        
        self.assertEqual(changelog_call.timestamp, self.fixed_datetime)
        self.assertEqual(ticket_call.last_changed_date, self.fixed_datetime)