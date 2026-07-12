import hashlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ApiConsumer


class TestHashToken(unittest.TestCase):
    def test_hash_token_returns_sha256_hex(self):
        from api.auth import hash_token

        token = "iron_abc123"
        expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
        self.assertEqual(hash_token(token), expected)

    def test_hash_token_deterministic(self):
        from api.auth import hash_token

        token = "iron_xyz"
        self.assertEqual(hash_token(token), hash_token(token))

    def test_hash_token_different_inputs_differ(self):
        from api.auth import hash_token

        self.assertNotEqual(hash_token("a"), hash_token("b"))


class TestVerifyBearer(unittest.IsolatedAsyncioTestCase):
    async def test_missing_authorization_raises_401(self):
        from api.auth import verify_bearer

        with self.assertRaises(HTTPException) as ctx:
            await verify_bearer(None, AsyncMock(spec=AsyncSession))
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_malformed_authorization_raises_401(self):
        from api.auth import verify_bearer

        with self.assertRaises(HTTPException) as ctx:
            await verify_bearer("NotBearer xyz", AsyncMock(spec=AsyncSession))
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_lowercase_bearer_raises_401(self):
        from api.auth import verify_bearer

        with self.assertRaises(HTTPException) as ctx:
            await verify_bearer("bearer iron_abc", AsyncMock(spec=AsyncSession))
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_token_not_found_raises_401(self):
        from api.auth import verify_bearer

        mock_session = AsyncMock(spec=AsyncSession)
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_execute_result

        with self.assertRaises(HTTPException) as ctx:
            await verify_bearer("Bearer iron_xyz", mock_session)
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_disabled_consumer_raises_401(self):
        from api.auth import verify_bearer

        consumer = MagicMock(spec=ApiConsumer)
        consumer.enabled = False

        mock_session = AsyncMock(spec=AsyncSession)
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = consumer
        mock_session.execute.return_value = mock_execute_result

        with self.assertRaises(HTTPException) as ctx:
            await verify_bearer("Bearer iron_xyz", mock_session)
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_valid_token_returns_consumer(self):
        from api.auth import verify_bearer

        consumer = MagicMock(spec=ApiConsumer)
        consumer.enabled = True

        mock_session = AsyncMock(spec=AsyncSession)
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one_or_none.return_value = consumer
        mock_session.execute.return_value = mock_execute_result

        result = await verify_bearer("Bearer iron_abc", mock_session)
        self.assertIs(result, consumer)

    async def test_uses_consumer_service_lookup(self):
        from api.auth import verify_bearer

        consumer = MagicMock(spec=ApiConsumer)
        consumer.enabled = True

        with patch(
            "api.auth.consumer_service.get_consumer_by_token_hash",
            new=AsyncMock(return_value=consumer),
        ) as mock_lookup:
            result = await verify_bearer(
                "Bearer iron_abc", AsyncMock(spec=AsyncSession)
            )

        self.assertIs(result, consumer)
        mock_lookup.assert_awaited_once()
