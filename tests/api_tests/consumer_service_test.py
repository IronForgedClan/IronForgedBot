import unittest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from api.consumer_service import (
    create_consumer,
    delete_consumer,
    generate_token,
    get_consumer_by_name,
    get_consumer_by_token_hash,
    grant_perm,
    list_consumers,
    revoke_perm,
    rotate_token,
    set_enabled,
    set_perms,
)
from api.models import ApiConsumer


def _mock_session() -> MagicMock:
    s = AsyncMock(spec=AsyncSession)
    return s


class TestGenerateToken(unittest.TestCase):
    def test_token_starts_with_prefix(self):
        token = generate_token()
        self.assertTrue(token.startswith("iron_"))

    def test_token_is_unique(self):
        self.assertNotEqual(generate_token(), generate_token())


class TestCreateConsumer(unittest.IsolatedAsyncioTestCase):
    async def test_creates_consumer_with_perms(self):
        session = _mock_session()
        consumer, token = await create_consumer(
            session, "statsite", perms=["members:read"], description="Stats dashboard"
        )
        self.assertEqual(consumer.name, "statsite")
        self.assertEqual(consumer.perms, ["members:read"])
        self.assertTrue(consumer.enabled)
        self.assertEqual(consumer.description, "Stats dashboard")
        self.assertTrue(token.startswith("iron_"))
        session.add.assert_awaited() if hasattr(session.add, "assert_awaited") else None
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once()

    async def test_creates_consumer_with_empty_perms(self):
        session = _mock_session()
        consumer, _ = await create_consumer(session, "minimal")
        self.assertEqual(consumer.perms, [])


class TestListConsumers(unittest.IsolatedAsyncioTestCase):
    async def test_returns_ordered_list(self):
        c1 = MagicMock(spec=ApiConsumer)
        c1.name = "a"
        c2 = MagicMock(spec=ApiConsumer)
        c2.name = "b"
        session = _mock_session()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [c1, c2]
        session.execute.return_value = result

        consumers = await list_consumers(session)
        self.assertEqual([c.name for c in consumers], ["a", "b"])


class TestGetConsumerByName(unittest.IsolatedAsyncioTestCase):
    async def test_found(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        result_consumer = await get_consumer_by_name(session, "tester")
        self.assertEqual(result_consumer.name, "tester")

    async def test_not_found_returns_none(self):
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        self.assertIsNone(await get_consumer_by_name(session, "ghost"))


class TestGetConsumerByTokenHash(unittest.IsolatedAsyncioTestCase):
    async def test_found(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        result_consumer = await get_consumer_by_token_hash(session, "abc123hash")
        self.assertEqual(result_consumer.name, "tester")

    async def test_not_found_returns_none(self):
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        self.assertIsNone(await get_consumer_by_token_hash(session, "missing"))

    async def test_queries_by_token_hash(self):
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        await get_consumer_by_token_hash(session, "thehash")

        query = session.execute.call_args[0][0]
        self.assertIn("token_hash", str(query).lower())


class TestGrantPerm(unittest.IsolatedAsyncioTestCase):
    async def test_grant_adds_perm(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        consumer.perms = ["scores:read"]

        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        updated = await grant_perm(session, "tester", "members:read")
        self.assertIn("members:read", updated.perms)
        self.assertIn("scores:read", updated.perms)

    async def test_grant_unknown_perm_raises(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        consumer.perms = []

        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        with self.assertRaises(ValueError) as ctx:
            await grant_perm(session, "tester", "bogus:perm")
        self.assertIn("bogus:perm", str(ctx.exception))

    async def test_grant_unknown_consumer_raises(self):
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        with self.assertRaises(ValueError) as ctx:
            await grant_perm(session, "ghost", "members:read")
        self.assertIn("ghost", str(ctx.exception))


class TestRevokePerm(unittest.IsolatedAsyncioTestCase):
    async def test_revoke_removes_perm(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        consumer.perms = ["members:read", "scores:read"]

        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        updated = await revoke_perm(session, "tester", "members:read")
        self.assertNotIn("members:read", updated.perms)
        self.assertIn("scores:read", updated.perms)


class TestSetPerms(unittest.IsolatedAsyncioTestCase):
    async def test_set_replaces_perms(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        consumer.perms = ["members:read"]

        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        updated = await set_perms(session, "tester", ["members:read", "scores:read"])
        self.assertEqual(set(updated.perms), {"members:read", "scores:read"})

    async def test_set_with_unknown_raises(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        consumer.perms = []

        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        with self.assertRaises(ValueError):
            await set_perms(session, "tester", ["bogus:perm"])


class TestRotateToken(unittest.IsolatedAsyncioTestCase):
    async def test_rotates_token(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        consumer.token_hash = "old"

        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        updated, new_token = await rotate_token(session, "tester")
        self.assertNotEqual(updated.token_hash, "old")
        self.assertTrue(new_token.startswith("iron_"))


class TestDeleteConsumer(unittest.IsolatedAsyncioTestCase):
    async def test_delete_existing(self):
        consumer = MagicMock(spec=ApiConsumer)
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        deleted = await delete_consumer(session, "tester")
        self.assertTrue(deleted)
        session.delete.assert_awaited_once_with(consumer)

    async def test_delete_missing_returns_false(self):
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        deleted = await delete_consumer(session, "ghost")
        self.assertFalse(deleted)


class TestSetEnabled(unittest.IsolatedAsyncioTestCase):
    async def test_enable(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        consumer.enabled = False
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        updated = await set_enabled(session, "tester", True)
        self.assertTrue(updated.enabled)

    async def test_disable(self):
        consumer = MagicMock(spec=ApiConsumer)
        consumer.name = "tester"
        consumer.enabled = True
        session = _mock_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = consumer
        session.execute.return_value = result

        updated = await set_enabled(session, "tester", False)
        self.assertFalse(updated.enabled)
