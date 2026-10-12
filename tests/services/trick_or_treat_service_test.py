import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from ironforgedbot.services.trick_or_treat_service import TrickOrTreatService


class TestTrickOrTreatService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = AsyncMock()
        self.transaction = AsyncMock()
        self.session.begin = MagicMock(return_value=self.transaction)
        self.source = SimpleNamespace(
            discord_id=1001, id="source", ingots=1000, last_changed_date=None
        )
        self.target = SimpleNamespace(
            discord_id=1002, id="target", ingots=5000, last_changed_date=None
        )
        query_result = MagicMock()
        query_result.scalars.return_value.all.return_value = [self.source, self.target]
        self.session.execute = AsyncMock(return_value=query_result)
        self.session.add_all = MagicMock()
        self.service = TrickOrTreatService(self.session)

    async def test_transfer_ingots_updates_both_members_in_one_transaction(self):
        result = await self.service.transfer_ingots(1001, 1002, 300, "Steal")

        self.assertTrue(result.status)
        self.assertEqual(result.amount, 300)
        self.assertEqual(result.source_total, 700)
        self.assertEqual(result.target_total, 5300)
        self.assertIsInstance(self.source.last_changed_date, datetime)
        self.assertEqual(self.source.last_changed_date, self.target.last_changed_date)
        self.session.add_all.assert_called_once()

    async def test_transfer_ingots_rejects_insufficient_balance_without_changes(self):
        result = await self.service.transfer_ingots(1001, 1002, 1500, "Steal")

        self.assertFalse(result.status)
        self.assertEqual(self.source.ingots, 1000)
        self.assertEqual(self.target.ingots, 5000)
        self.session.add_all.assert_not_called()
