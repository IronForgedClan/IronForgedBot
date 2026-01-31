from datetime import datetime, timedelta
import unittest
from unittest.mock import AsyncMock, Mock, patch

import discord

from ironforgedbot.tasks.job_payroll import (
    get_payment_month,
    pay_group,
    job_payroll,
    LEADERSHIP_PAYMENT,
    STAFF_PAYMENT,
    BOOSTER_PAYMENT,
)
from tests.helpers import create_test_db_member


class TestGetPaymentMonth(unittest.TestCase):
    """Unit tests for get_payment_month function."""

    @patch("ironforgedbot.tasks.job_payroll.datetime")
    def test_returns_previous_month_name(self, mock_datetime):
        """Test that it returns the previous month's name."""
        mock_datetime.now.return_value = datetime(2024, 3, 15)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        result = get_payment_month()

        self.assertEqual(result, "February")

    @patch("ironforgedbot.tasks.job_payroll.datetime")
    def test_january_returns_december(self, mock_datetime):
        """Test that January returns December (previous year)."""
        mock_datetime.now.return_value = datetime(2024, 1, 5)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        result = get_payment_month()

        self.assertEqual(result, "December")

    @patch("ironforgedbot.tasks.job_payroll.datetime")
    def test_first_of_month_returns_previous_month(self, mock_datetime):
        """Test that the 1st of a month correctly returns previous month."""
        mock_datetime.now.return_value = datetime(2024, 6, 1)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        result = get_payment_month()

        self.assertEqual(result, "May")


class TestPayGroup(unittest.IsolatedAsyncioTestCase):
    """Unit tests for pay_group function."""

    def setUp(self):
        self.mock_ingot_service = AsyncMock()

    async def test_successful_payment(self):
        """Test successful payment for all members in group."""
        members = [
            create_test_db_member(nickname="Leader1", discord_id=1001),
            create_test_db_member(nickname="Leader2", discord_id=1002),
        ]

        self.mock_ingot_service.try_add_ingots.return_value = Mock(
            status=True, new_total=50000, message="Success"
        )

        result = await pay_group(
            self.mock_ingot_service, members, 25000, "Test payment"
        )

        self.assertEqual(self.mock_ingot_service.try_add_ingots.call_count, 2)
        self.assertIn("Leader1", result)
        self.assertIn("Leader2", result)
        self.assertIn("+25,000", result)
        self.assertIn("50,000", result)

    async def test_payment_failure_logged(self):
        """Test that payment failures are recorded in output."""
        members = [create_test_db_member(nickname="FailMember", discord_id=2001)]

        self.mock_ingot_service.try_add_ingots.return_value = Mock(
            status=False, new_total=1000, message="Insufficient funds"
        )

        result = await pay_group(self.mock_ingot_service, members, 5000, "Test payment")

        self.assertIn("FailMember", result)
        self.assertIn("0", result)
        self.assertIn("1,000", result)

    async def test_exception_handling_continues_processing(self):
        """Test that exceptions don't stop processing other members."""
        members = [
            create_test_db_member(nickname="ErrorMember", discord_id=3001),
            create_test_db_member(nickname="SuccessMember", discord_id=3002),
        ]

        self.mock_ingot_service.try_add_ingots.side_effect = [
            Exception("Database error"),
            Mock(status=True, new_total=10000, message="Success"),
        ]

        result = await pay_group(self.mock_ingot_service, members, 5000, "Test payment")

        self.assertIn("SuccessMember", result)
        self.assertIn("+5,000", result)
        self.assertNotIn("ErrorMember", result)

    async def test_empty_group_returns_empty_table(self):
        """Test that empty group returns empty table."""
        result = await pay_group(self.mock_ingot_service, [], 5000, "Test payment")

        self.mock_ingot_service.try_add_ingots.assert_not_called()
        self.assertIn("Member", result)
        self.assertIn("Change", result)
        self.assertIn("Total", result)

    async def test_invalid_payment_result_logged(self):
        """Test that None/invalid payment results are handled."""
        members = [create_test_db_member(nickname="InvalidMember", discord_id=4001)]

        self.mock_ingot_service.try_add_ingots.return_value = None

        result = await pay_group(self.mock_ingot_service, members, 5000, "Test payment")

        self.assertIn("InvalidMember", result)
        self.assertIn("0", result)
        self.assertIn("?", result)


class TestJobPayroll(unittest.IsolatedAsyncioTestCase):
    """Integration tests for job_payroll function."""

    def setUp(self):
        self.mock_report_channel = Mock(spec=discord.TextChannel)
        self.mock_report_channel.send = AsyncMock()

    @patch("ironforgedbot.tasks.job_payroll.report_payroll")
    @patch("ironforgedbot.tasks.job_payroll.pay_group")
    @patch("ironforgedbot.tasks.job_payroll.create_ingot_service")
    @patch("ironforgedbot.tasks.job_payroll.create_member_service")
    @patch("ironforgedbot.tasks.job_payroll.db")
    @patch("ironforgedbot.tasks.job_payroll.get_payment_month")
    async def test_pays_all_groups(
        self,
        mock_get_month,
        mock_db,
        mock_create_member_service,
        mock_create_ingot_service,
        mock_pay_group,
        mock_report_payroll,
    ):
        """Test that all three groups are paid."""
        mock_get_month.return_value = "January"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_active_members_by_role.side_effect = [
            [create_test_db_member(nickname="Leader", discord_id=1)],
            [create_test_db_member(nickname="Staff", discord_id=2)],
        ]
        mock_member_service.get_active_boosters.return_value = [
            create_test_db_member(nickname="Booster", discord_id=3)
        ]
        mock_create_member_service.return_value = mock_member_service

        mock_ingot_service = AsyncMock()
        mock_create_ingot_service.return_value = mock_ingot_service

        mock_pay_group.return_value = "| Member | Change | Total |"

        await job_payroll(self.mock_report_channel)

        self.assertEqual(mock_pay_group.call_count, 3)
        self.assertEqual(mock_report_payroll.call_count, 3)

        call_args = [call.args for call in mock_pay_group.call_args_list]
        payments = [args[2] for args in call_args]
        self.assertIn(LEADERSHIP_PAYMENT, payments)
        self.assertIn(STAFF_PAYMENT, payments)
        self.assertIn(BOOSTER_PAYMENT, payments)

    @patch("ironforgedbot.tasks.job_payroll.report_payroll")
    @patch("ironforgedbot.tasks.job_payroll.pay_group")
    @patch("ironforgedbot.tasks.job_payroll.create_ingot_service")
    @patch("ironforgedbot.tasks.job_payroll.create_member_service")
    @patch("ironforgedbot.tasks.job_payroll.db")
    @patch("ironforgedbot.tasks.job_payroll.get_payment_month")
    async def test_leadership_excluded_from_staff(
        self,
        mock_get_month,
        mock_db,
        mock_create_member_service,
        mock_create_ingot_service,
        mock_pay_group,
        mock_report_payroll,
    ):
        """Test that leadership members are excluded from staff payments."""
        mock_get_month.return_value = "January"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        leader = create_test_db_member(nickname="LeaderStaff", discord_id=100)

        mock_member_service = AsyncMock()
        mock_member_service.get_active_members_by_role.side_effect = [
            [leader],
            [leader, create_test_db_member(nickname="OnlyStaff", discord_id=200)],
        ]
        mock_member_service.get_active_boosters.return_value = []
        mock_create_member_service.return_value = mock_member_service

        mock_ingot_service = AsyncMock()
        mock_create_ingot_service.return_value = mock_ingot_service

        mock_pay_group.return_value = "| Member | Change | Total |"

        await job_payroll(self.mock_report_channel)

        staff_call = mock_pay_group.call_args_list[1]
        staff_members = staff_call.args[1]

        self.assertEqual(len(staff_members), 1)
        self.assertEqual(staff_members[0].nickname, "OnlyStaff")

    @patch("ironforgedbot.tasks.job_payroll.report_payroll")
    @patch("ironforgedbot.tasks.job_payroll.pay_group")
    @patch("ironforgedbot.tasks.job_payroll.create_ingot_service")
    @patch("ironforgedbot.tasks.job_payroll.create_member_service")
    @patch("ironforgedbot.tasks.job_payroll.db")
    @patch("ironforgedbot.tasks.job_payroll.get_payment_month")
    async def test_empty_groups_handled(
        self,
        mock_get_month,
        mock_db,
        mock_create_member_service,
        mock_create_ingot_service,
        mock_pay_group,
        mock_report_payroll,
    ):
        """Test that empty groups are handled gracefully."""
        mock_get_month.return_value = "January"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_active_members_by_role.return_value = []
        mock_member_service.get_active_boosters.return_value = []
        mock_create_member_service.return_value = mock_member_service

        mock_ingot_service = AsyncMock()
        mock_create_ingot_service.return_value = mock_ingot_service

        mock_pay_group.return_value = "| Member | Change | Total |"

        await job_payroll(self.mock_report_channel)

        self.assertEqual(mock_pay_group.call_count, 3)

        for call in mock_pay_group.call_args_list:
            group = call.args[1]
            self.assertEqual(len(group), 0)

    @patch("ironforgedbot.tasks.job_payroll.report_payroll")
    @patch("ironforgedbot.tasks.job_payroll.pay_group")
    @patch("ironforgedbot.tasks.job_payroll.create_ingot_service")
    @patch("ironforgedbot.tasks.job_payroll.create_member_service")
    @patch("ironforgedbot.tasks.job_payroll.db")
    @patch("ironforgedbot.tasks.job_payroll.get_payment_month")
    async def test_correct_payment_reasons(
        self,
        mock_get_month,
        mock_db,
        mock_create_member_service,
        mock_create_ingot_service,
        mock_pay_group,
        mock_report_payroll,
    ):
        """Test that payment reasons include the month name."""
        mock_get_month.return_value = "February"

        mock_session = AsyncMock()
        mock_db.get_session.return_value.__aenter__.return_value = mock_session

        mock_member_service = AsyncMock()
        mock_member_service.get_active_members_by_role.return_value = []
        mock_member_service.get_active_boosters.return_value = []
        mock_create_member_service.return_value = mock_member_service

        mock_ingot_service = AsyncMock()
        mock_create_ingot_service.return_value = mock_ingot_service

        mock_pay_group.return_value = "| Member | Change | Total |"

        await job_payroll(self.mock_report_channel)

        reasons = [call.args[3] for call in mock_pay_group.call_args_list]

        self.assertTrue(all("February" in reason for reason in reasons))
        self.assertIn("February leadership payment", reasons)
        self.assertIn("February staff payment", reasons)
        self.assertIn("February booster payment", reasons)


if __name__ == "__main__":
    unittest.main()
