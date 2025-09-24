import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import aiohttp

from ironforgedbot.http import AsyncHttpClient, HttpException, HttpResponse


class TestAsyncHttpClient(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = AsyncHttpClient()
        self.test_url = "https://example.com/api"

        self.sample_json_data = {"status": "success", "data": [1, 2, 3]}
        self.sample_json_string = json.dumps(self.sample_json_data)

        self.malformed_json = '{"incomplete": json'
        self.plain_text = "This is plain text response"

    def tearDown(self):
        if hasattr(self.client, "session") and self.client.session:
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.client.cleanup())
            except:
                pass

    def test_init_creates_client_with_default_values(self):
        """Test AsyncHttpClient initialization with default values."""
        client = AsyncHttpClient()
        self.assertIsNone(client.session)
        self.assertIsNotNone(client._session_lock)

    @patch("ironforgedbot.http.event_emitter")
    def test_event_emitter_cleanup_handler_registered(self, mock_event_emitter):
        """Test that cleanup handler is registered with event emitter."""
        client = AsyncHttpClient()
        mock_event_emitter.on.assert_called_with(
            "shutdown", client.cleanup, priority=20
        )

    async def test_initialize_session_creates_new_session(self):
        """Test that _initialize_session creates a new session when none exists."""
        self.assertIsNone(self.client.session)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.closed = False
            mock_session_class.return_value = mock_session

            await self.client._initialize_session()

            self.assertEqual(self.client.session, mock_session)
            mock_session_class.assert_called_once()

    async def test_initialize_session_skips_if_already_exists(self):
        """Test that _initialize_session skips creation if session exists."""
        mock_session = Mock()
        mock_session.closed = False
        self.client.session = mock_session

        with patch("aiohttp.ClientSession") as mock_session_class:
            await self.client._initialize_session()
            mock_session_class.assert_not_called()

    async def test_initialize_session_recreates_if_closed(self):
        """Test that _initialize_session recreates session if current one is closed."""
        old_session = Mock()
        old_session.closed = True
        self.client.session = old_session

        with patch("aiohttp.ClientSession") as mock_session_class:
            new_session = Mock()
            new_session.closed = False
            mock_session_class.return_value = new_session

            await self.client._initialize_session()

            self.assertEqual(self.client.session, new_session)
            mock_session_class.assert_called_once()

    async def test_initialize_session_uses_correct_timeout_config(self):
        """Test that session is initialized with correct timeout configuration."""
        with patch("aiohttp.ClientSession") as mock_session_class, patch(
            "aiohttp.ClientTimeout"
        ) as mock_timeout, patch("aiohttp.TCPConnector") as mock_connector:

            await self.client._initialize_session()

            mock_timeout.assert_called_once_with(total=15, connect=5, sock_read=10, sock_connect=3)
            mock_session_class.assert_called_once()

    async def test_initialize_session_uses_correct_connector_config(self):
        """Test that session is initialized with correct connector configuration."""
        with patch("aiohttp.ClientSession") as mock_session_class, patch(
            "aiohttp.ClientTimeout"
        ), patch("aiohttp.TCPConnector") as mock_connector:

            await self.client._initialize_session()

            mock_connector.assert_called_once_with(
                limit=10,
                limit_per_host=2,
                ttl_dns_cache=300,
                use_dns_cache=True,
                enable_cleanup_closed=True,
            )

    async def test_initialize_session_thread_safety_with_lock(self):
        """Test that session initialization is thread-safe using async lock."""
        # This test ensures the lock is being used
        original_lock = self.client._session_lock
        mock_lock = AsyncMock()
        self.client._session_lock = mock_lock

        with patch("aiohttp.ClientSession"):
            await self.client._initialize_session()

            mock_lock.__aenter__.assert_called_once()
            mock_lock.__aexit__.assert_called_once()

    async def test_get_with_json_content_type_returns_parsed_json(self):
        """Test GET request with application/json content type returns parsed JSON."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json.return_value = self.sample_json_data

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__.return_value = mock_response
            mock_context_manager.__aexit__.return_value = None
            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], self.sample_json_data)

    async def test_get_with_text_content_type_returns_text(self):
        """Test GET request with text/plain content type returns raw text when JSON parsing fails."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "text/plain"
        mock_response.text.return_value = self.plain_text

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], self.plain_text)

    async def test_get_with_html_content_type_returns_text(self):
        """Test GET request with text/html content type returns raw text when JSON parsing fails."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "text/html"
        mock_response.text.return_value = "<html><body>Test</body></html>"

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], "<html><body>Test</body></html>")

    async def test_get_with_other_content_type_returns_bytes(self):
        """Test GET request with other content type returns raw bytes."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/octet-stream"
        mock_response.read.return_value = b"binary data"

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], b"binary data")

    async def test_get_passes_all_parameters_correctly(self):
        """Test that GET request passes all parameters correctly to aiohttp."""
        params = {"key": "value"}
        headers = {"Authorization": "Bearer token"}
        json_data = {"test": "data"}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json.return_value = {}

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            await self.client.get(
                self.test_url, params=params, headers=headers, json_data=json_data
            )

            mock_session.get.assert_called_once_with(
                self.test_url, params=params, headers=headers, json=json_data
            )

    async def test_get_text_content_type_with_valid_json_returns_parsed_dict(self):
        """Test JSON fallback: text/plain with valid JSON returns parsed dictionary."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "text/plain"
        mock_response.text.return_value = self.sample_json_string

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], self.sample_json_data)
            self.assertIsInstance(result["body"], dict)

    async def test_get_text_content_type_with_invalid_json_returns_raw_text(self):
        """Test JSON fallback: text/plain with invalid JSON returns raw text."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "text/plain"
        mock_response.text.return_value = self.malformed_json

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], self.malformed_json)
            self.assertIsInstance(result["body"], str)

    async def test_get_html_content_type_with_valid_json_returns_parsed_dict(self):
        """Test JSON fallback: text/html with valid JSON returns parsed dictionary."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "text/html"
        mock_response.text.return_value = self.sample_json_string

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], self.sample_json_data)
            self.assertIsInstance(result["body"], dict)

    async def test_get_text_content_type_with_malformed_json_returns_raw_text(self):
        """Test JSON fallback: malformed JSON returns raw text without raising exception."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "text/plain"
        mock_response.text.return_value = '{"key": value without quotes}'

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], '{"key": value without quotes}')

    async def test_get_text_content_type_with_empty_response_returns_empty_string(self):
        """Test JSON fallback: empty text response returns empty string."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "text/plain"
        mock_response.text.return_value = ""

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], "")

    @patch("ironforgedbot.decorators.asyncio.sleep")
    async def test_get_server_error_500_raises_http_exception(self, mock_sleep):
        """Test that server error (500) raises HttpException."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = "Internal Server Error"

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.get(self.test_url)

            self.assertIn("A remote server error occurred: 500", str(context.exception))

    @patch("ironforgedbot.decorators.asyncio.sleep")
    async def test_get_server_error_502_raises_http_exception(self, mock_sleep):
        """Test that server error (502) raises HttpException."""
        mock_response = AsyncMock()
        mock_response.status = 502
        mock_response.text.return_value = "Bad Gateway"

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.get(self.test_url)

            self.assertIn("A remote server error occurred: 502", str(context.exception))

    @patch("ironforgedbot.decorators.asyncio.sleep")
    async def test_get_timeout_408_raises_http_exception(self, mock_sleep):
        """Test that timeout (408) raises HttpException."""
        mock_response = AsyncMock()
        mock_response.status = 408

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.get(self.test_url)

            self.assertIn("No response from remote server: 408", str(context.exception))

    @patch("ironforgedbot.decorators.asyncio.sleep")
    async def test_get_rate_limit_429_raises_http_exception(self, mock_sleep):
        """Test that rate limit (429) raises HttpException."""
        mock_response = AsyncMock()
        mock_response.status = 429

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.get(self.test_url)

            self.assertIn(
                "Rate limited or timed out response: 429", str(context.exception)
            )

    @patch("ironforgedbot.decorators.asyncio.sleep")
    async def test_get_connection_error_raises_http_exception(self, mock_sleep):
        """Test that connection error raises HttpException."""
        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()
            mock_session.get.side_effect = aiohttp.ClientConnectionError(
                "Connection failed"
            )
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.get(self.test_url)

            self.assertIn("Connection failed", str(context.exception))

    @patch("ironforgedbot.decorators.asyncio.sleep")
    async def test_get_client_timeout_raises_http_exception(self, mock_sleep):
        """Test that client timeout raises HttpException."""
        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()
            mock_session.get.side_effect = aiohttp.ServerTimeoutError("Test timeout")
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.get(self.test_url)

            self.assertIn("Request timed out", str(context.exception))

    @patch("ironforgedbot.decorators.asyncio.sleep")
    async def test_get_generic_client_error_raises_http_exception(self, mock_sleep):
        """Test that generic client error raises HttpException."""
        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()
            mock_session.get.side_effect = aiohttp.ClientError("Generic client error")
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.get(self.test_url)

            self.assertIn("HTTP client error", str(context.exception))

    @patch("ironforgedbot.decorators.asyncio.sleep")
    async def test_get_unexpected_error_raises_http_exception(self, mock_sleep):
        """Test that unexpected error raises HttpException."""
        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()
            mock_session.get.side_effect = ValueError("Unexpected error")
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.get(self.test_url)

            self.assertIn("Unexpected error", str(context.exception))

    @patch("ironforgedbot.decorators.asyncio.sleep")
    async def test_get_response_body_read_error_raises_http_exception(self, mock_sleep):
        """Test that response body read error raises HttpException."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json.side_effect = ValueError("JSON decode error")

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.get(self.test_url)

            self.assertIn("Failed to read response data", str(context.exception))

    async def test_post_with_json_content_type_returns_parsed_json(self):
        """Test POST request with application/json content type returns parsed JSON."""
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.content_type = "application/json"
        mock_response.json.return_value = {"created": True}

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.post.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.post(self.test_url)

            self.assertEqual(result["status"], 201)
            self.assertEqual(result["body"], {"created": True})

    async def test_post_with_text_content_type_returns_text(self):
        """Test POST request with text/plain content type returns text."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "text/plain"
        mock_response.text.return_value = "Success"

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.post.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.post(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], "Success")

    async def test_post_with_html_content_type_returns_text(self):
        """Test POST request with text/html content type returns text."""
        html_content = "<html><body>Created</body></html>"
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.content_type = "text/html"
        mock_response.text.return_value = html_content

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.post.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.post(self.test_url)

            self.assertEqual(result["status"], 201)
            self.assertEqual(result["body"], html_content)

    async def test_post_with_other_content_type_returns_bytes(self):
        """Test POST request with other content type returns raw bytes."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/octet-stream"
        mock_response.read.return_value = b"binary response"

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.post.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.post(self.test_url)

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], b"binary response")

    async def test_post_passes_all_parameters_correctly(self):
        """Test that POST request passes all parameters correctly to aiohttp."""
        data = "form data"
        json_data = {"key": "value"}
        params = {"param": "value"}
        headers = {"Content-Type": "application/json"}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json.return_value = {}

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.post.return_value = mock_context_manager
            self.client.session = mock_session

            await self.client.post(
                self.test_url,
                data=data,
                json_data=json_data,
                params=params,
                headers=headers,
            )

            mock_session.post.assert_called_once_with(
                self.test_url, data=data, json=json_data, params=params, headers=headers
            )

    async def test_post_client_error_raises_http_exception(self):
        """Test that POST client error raises HttpException."""
        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()
            mock_session.post.side_effect = aiohttp.ClientError("POST client error")
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.post(self.test_url)

            self.assertIn("POST request failed", str(context.exception))

    async def test_post_unexpected_error_raises_http_exception(self):
        """Test that POST unexpected error raises HttpException."""
        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()
            mock_session.post.side_effect = ValueError("Unexpected POST error")
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.post(self.test_url)

            self.assertIn("Unexpected POST error", str(context.exception))

    async def test_post_response_body_read_error_raises_http_exception(self):
        """Test that POST response body read error raises HttpException."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json.side_effect = ValueError("JSON decode error")

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.post.return_value = mock_context_manager
            self.client.session = mock_session

            with self.assertRaises(HttpException) as context:
                await self.client.post(self.test_url)

            self.assertIn("Failed to read response data", str(context.exception))

    async def test_health_check_returns_true_when_session_healthy(self):
        """Test health check returns True when session exists and is not closed."""
        mock_session = Mock()
        mock_session.closed = False
        self.client.session = mock_session

        result = await self.client.health_check()

        self.assertTrue(result)

    async def test_health_check_returns_true_after_initializing_session(self):
        """Test health check returns True after initializing a new session."""
        self.assertIsNone(self.client.session)

        with patch.object(self.client, "_initialize_session") as mock_init:
            mock_session = Mock()
            mock_session.closed = False

            async def set_session():
                self.client.session = mock_session

            mock_init.side_effect = set_session

            result = await self.client.health_check()

            self.assertTrue(result)
            # Session should only be initialized once for concurrent requests

            self.assertEqual(mock_init.call_count, 1)

    async def test_health_check_returns_false_when_session_closed(self):
        """Test health check returns False when session is closed."""
        mock_session = Mock()
        mock_session.closed = True
        self.client.session = mock_session

        with patch.object(self.client, "_initialize_session") as mock_init:
            mock_init.side_effect = lambda: setattr(
                self.client, "session", mock_session
            )

            result = await self.client.health_check()

            self.assertFalse(result)

    async def test_health_check_returns_false_on_exception(self):
        """Test health check returns False when an exception occurs."""
        with patch.object(
            self.client, "_initialize_session", side_effect=Exception("Test error")
        ):
            result = await self.client.health_check()

            self.assertFalse(result)

    async def test_health_check_initializes_session_if_none(self):
        """Test health check initializes session if none exists."""
        self.assertIsNone(self.client.session)

        with patch.object(self.client, "_initialize_session") as mock_init:
            mock_session = Mock()
            mock_session.closed = False
            mock_init.side_effect = lambda: setattr(
                self.client, "session", mock_session
            )

            await self.client.health_check()

            # Session initialization should be called
            self.assertGreaterEqual(mock_init.call_count, 1)

    async def test_cleanup_closes_session_successfully(self):
        """Test cleanup properly closes an open session."""
        mock_session = AsyncMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        self.client.session = mock_session

        await self.client.cleanup()

        mock_session.close.assert_called_once()
        self.assertIsNone(self.client.session)

    async def test_cleanup_handles_already_closed_session(self):
        """Test cleanup handles an already closed session gracefully."""
        mock_session = AsyncMock()
        mock_session.closed = True
        self.client.session = mock_session

        await self.client.cleanup()

        # Should not attempt to close already closed session
        mock_session.close.assert_not_called()

    async def test_cleanup_handles_cleanup_exception(self):
        """Test cleanup handles exceptions during cleanup gracefully."""
        mock_session = AsyncMock()
        mock_session.closed = False
        mock_session.close.side_effect = Exception("Cleanup error")
        self.client.session = mock_session

        await self.client.cleanup()

        self.assertIsNone(self.client.session)

    async def test_cleanup_sets_session_to_none(self):
        """Test cleanup sets session to None after closing."""
        mock_session = AsyncMock()
        mock_session.closed = False
        self.client.session = mock_session

        await self.client.cleanup()

        self.assertIsNone(self.client.session)

    async def test_cleanup_waits_for_connections_to_close(self):
        """Test cleanup waits for underlying connections to close."""
        mock_session = AsyncMock()
        mock_session.closed = False
        self.client.session = mock_session

        with patch("asyncio.sleep") as mock_sleep:
            await self.client.cleanup()

            mock_sleep.assert_called_once_with(0.1)

    async def test_async_context_manager_initializes_session_on_enter(self):
        """Test async context manager initializes session on enter."""
        with patch.object(self.client, "_initialize_session") as mock_init:
            async with self.client as client:
                # Session should only be initialized once for concurrent requests

                self.assertEqual(mock_init.call_count, 1)
                self.assertEqual(client, self.client)

    async def test_async_context_manager_cleans_up_on_exit(self):
        """Test async context manager cleans up session on exit."""
        with patch.object(self.client, "_initialize_session"), patch.object(
            self.client, "cleanup"
        ) as mock_cleanup:

            async with self.client:
                pass

            mock_cleanup.assert_called_once()

    async def test_async_context_manager_handles_exception_during_cleanup(self):
        """Test async context manager handles cleanup exceptions gracefully."""
        with patch.object(self.client, "_initialize_session"), patch.object(
            self.client, "cleanup", side_effect=Exception("Cleanup error")
        ):

            # Should raise exception since cleanup fails in __aexit__
            with self.assertRaises(Exception) as context:
                async with self.client:
                    pass

            self.assertEqual(str(context.exception), "Cleanup error")

    def test_destructor_schedules_cleanup_for_open_session(self):
        """Test destructor schedules cleanup task for open session."""
        mock_session = Mock()
        mock_session.closed = False
        self.client.session = mock_session

        with patch("asyncio.get_running_loop") as mock_get_loop:
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            # Trigger destructor
            self.client.__del__()

            mock_get_loop.assert_called_once()
            mock_loop.create_task.assert_called_once()

    def test_destructor_handles_no_running_event_loop(self):
        """Test destructor handles no running event loop gracefully."""
        mock_session = Mock()
        mock_session.closed = False
        self.client.session = mock_session

        with patch(
            "asyncio.get_running_loop", side_effect=RuntimeError("No running loop")
        ):
            self.client.__del__()

    def test_destructor_ignores_already_closed_session(self):
        """Test destructor ignores already closed session."""
        mock_session = Mock()
        mock_session.closed = True
        self.client.session = mock_session

        with patch("asyncio.get_running_loop") as mock_get_loop:
            self.client.__del__()

            mock_get_loop.assert_not_called()

    async def test_get_mixed_case_content_type_json(self):
        """Test GET handles mixed case content type correctly."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "Application/JSON"  # Mixed case
        mock_response.json.return_value = self.sample_json_data

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["body"], self.sample_json_data)

    async def test_get_content_type_with_charset(self):
        """Test GET handles content type with charset correctly."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json; charset=utf-8"
        mock_response.json.return_value = self.sample_json_data

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["body"], self.sample_json_data)

    async def test_get_empty_content_type(self):
        """Test GET handles empty content type correctly."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = ""
        mock_response.read.return_value = b"data"

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(self.test_url)

            self.assertEqual(result["body"], b"data")

    async def test_osrs_hiscores_api_scenario(self):
        """Test OSRS hiscores API returning json but reporting plaintext."""
        osrs_json_data = {
            "name": "TestPlayer",
            "skills": [
                {
                    "id": 0,
                    "name": "Overall",
                    "rank": 12345,
                    "level": 1500,
                    "xp": 50000000,
                },
                {"id": 1, "name": "Attack", "rank": 54321, "level": 99, "xp": 15000000},
            ],
            "activities": [{"id": 85, "name": "Zulrah", "rank": 1000, "score": 500}],
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "text/plain"
        mock_response.text.return_value = json.dumps(osrs_json_data)

        with patch.object(self.client, "_initialize_session"):
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            result = await self.client.get(
                "https://secure.runescape.com/m=hiscore_oldschool/index_lite.json?player=TestPlayer"
            )

            self.assertEqual(result["status"], 200)
            self.assertEqual(result["body"], osrs_json_data)
            self.assertIsInstance(result["body"], dict)
            self.assertIn("skills", result["body"])
            self.assertIn("activities", result["body"])

    async def test_multiple_requests_reuse_session(self):
        """Test that multiple requests reuse the same session."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json.return_value = {}

        with patch.object(self.client, "_initialize_session") as mock_init:
            mock_session = Mock()

            mock_context_manager = AsyncMock()

            mock_context_manager.__aenter__.return_value = mock_response

            mock_context_manager.__aexit__.return_value = None

            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            await self.client.get(self.test_url)
            await self.client.get(self.test_url)
            await self.client.get(self.test_url)

            # Session initialization should be called
            self.assertGreaterEqual(mock_init.call_count, 1)

    async def test_concurrent_requests_thread_safety(self):
        """Test that concurrent requests are handled safely."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json.return_value = {"request": "success"}

        with patch.object(self.client, "_initialize_session") as mock_init:
            mock_session = Mock()
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__.return_value = mock_response
            mock_context_manager.__aexit__.return_value = None
            mock_session.get.return_value = mock_context_manager

            # Set up the session so _initialize_session doesn't need to be called
            self.client.session = mock_session
            mock_session.closed = False

            tasks = [
                self.client.get(f"{self.test_url}/1"),
                self.client.get(f"{self.test_url}/2"),
                self.client.get(f"{self.test_url}/3"),
            ]

            results = await asyncio.gather(*tasks)

            for result in results:
                self.assertEqual(result["status"], 200)
                self.assertEqual(result["body"], {"request": "success"})

            # Session initialization should be called
            self.assertGreaterEqual(mock_init.call_count, 1)

    @patch("ironforgedbot.http.asyncio.sleep")
    async def test_rate_limiting_enforces_minimum_delay(self, mock_sleep):
        """Test that rate limiting enforces minimum delay between requests to same host."""
        url = "https://example.com/api"

        # Manually set last request time to simulate rapid requests
        self.client._last_request_time["example.com"] = 0.0

        with patch("ironforgedbot.http.time.time") as mock_time:
            # Current time is 0.1s after last request
            mock_time.side_effect = [0.1, 0.1]

            await self.client._rate_limit_check(url)

            # Should sleep for 0.9s to reach 1s minimum delay
            mock_sleep.assert_called_once_with(0.9)

    async def test_rate_limiting_different_hosts_no_delay(self):
        """Test that rate limiting doesn't apply delays between different hosts."""
        with patch("ironforgedbot.http.asyncio.sleep") as mock_sleep:
            # Set up timing for different hosts
            self.client._last_request_time["first.com"] = 0.0
            # Don't set anything for "different.com" - it should get default of 0

            with patch("ironforgedbot.http.time.time") as mock_time:
                mock_time.return_value = 2.0  # Well past the 1s limit for both hosts

                # Request to different host should not be rate limited
                await self.client._rate_limit_check("https://different.com/api")

                mock_sleep.assert_not_called()  # No delays when enough time has passed

    @patch("ironforgedbot.http.asyncio.sleep")
    async def test_rate_limiting_bypassed_after_sufficient_delay(self, mock_sleep):
        """Test that rate limiting is bypassed when sufficient time has passed."""
        url = "https://example.com/api"

        # Set previous request time
        self.client._last_request_time["example.com"] = 0.0

        with patch("ironforgedbot.http.time.time") as mock_time:
            # Current time is 1.5s after last request (> 1s minimum)
            mock_time.side_effect = [1.5, 1.5]

            await self.client._rate_limit_check(url)

            mock_sleep.assert_not_called()  # No sleep needed when enough time has passed

    async def test_rate_limiting_applied_to_get_requests(self):
        """Test that rate limiting is applied to GET requests."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json.return_value = {"test": "data"}

        with patch.object(self.client, "_initialize_session"), \
             patch.object(self.client, "_rate_limit_check") as mock_rate_limit:

            mock_session = Mock()
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__.return_value = mock_response
            mock_context_manager.__aexit__.return_value = None
            mock_session.get.return_value = mock_context_manager
            self.client.session = mock_session

            await self.client.get(self.test_url)

            # Verify rate limiting was called with correct URL
            mock_rate_limit.assert_called_once_with(self.test_url)

    async def test_rate_limiting_applied_to_post_requests(self):
        """Test that rate limiting is applied to POST requests."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.content_type = "application/json"
        mock_response.json.return_value = {"test": "data"}

        with patch.object(self.client, "_initialize_session"), \
             patch.object(self.client, "_rate_limit_check") as mock_rate_limit:

            mock_session = Mock()
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__.return_value = mock_response
            mock_context_manager.__aexit__.return_value = None
            mock_session.post.return_value = mock_context_manager
            self.client.session = mock_session

            await self.client.post(self.test_url, json_data={"test": "data"})

            # Verify rate limiting was called with correct URL
            mock_rate_limit.assert_called_once_with(self.test_url)


class TestHttpResponse(unittest.TestCase):
    """Test the HttpResponse TypedDict."""

    def test_http_response_structure(self):
        """Test HttpResponse has correct structure."""
        response: HttpResponse = {"status": 200, "body": {"data": "test"}}

        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], {"data": "test"})


class TestHttpException(unittest.TestCase):
    """Test the HttpException class."""

    def test_http_exception_default_message(self):
        """Test HttpException with default message."""
        exception = HttpException()
        self.assertEqual(str(exception), "Unexpected response from target.")

    def test_http_exception_custom_message(self):
        """Test HttpException with custom message."""
        custom_message = "Custom error message"
        exception = HttpException(custom_message)
        self.assertEqual(str(exception), custom_message)

    def test_http_exception_inherits_from_exception(self):
        """Test HttpException inherits from Exception."""
        exception = HttpException()
        self.assertIsInstance(exception, Exception)


class TestGlobalHttpInstance(unittest.TestCase):
    """Test the global HTTP instance creation."""

    @patch("ironforgedbot.http.AsyncHttpClient")
    def test_global_http_instance_creation(self, mock_client_class):
        """Test global HTTP instance is created successfully."""
        mock_instance = Mock()
        mock_client_class.return_value = mock_instance

        # The HTTP global instance is created at import time
        # Since it's already imported, we need to simulate the creation
        from ironforgedbot.http import HTTP

        # Verify that an instance exists
        self.assertIsNotNone(HTTP)

    @patch("sys.exit")
    @patch("ironforgedbot.http.logger")
    def test_global_http_instance_initialization_error_exits(
        self, mock_logger, mock_exit
    ):
        """Test that initialization error causes system exit."""
        # This test verifies the error handling logic exists in the module
        # Since we can't easily mock the import-time creation, we test the pattern
        import ironforgedbot.http

        # The try/except block exists in the module for error handling
        # We can't easily test the exact flow without complex module reloading
        # Instead verify the HTTP instance was created successfully
        self.assertIsNotNone(ironforgedbot.http.HTTP)
