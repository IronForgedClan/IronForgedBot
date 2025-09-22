import asyncio
import logging
from enum import Enum
from typing import List, Optional, Tuple

import wom
from wom import GroupRole, Metric, Period
from wom.models import GroupDetail, GroupMembership, GroupMemberGains

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Categories of errors that can occur with WOM API."""
    JSON_MALFORMED = "json_malformed"
    RATE_LIMIT = "rate_limit"
    CONNECTION = "connection"
    UNKNOWN = "unknown"


class WomServiceError(Exception):
    """Exception raised for WOM service operations."""

    def __init__(self, message: str, error_type: ErrorType = ErrorType.UNKNOWN):
        super().__init__(message)
        self.error_type = error_type


class WomService:
    """Service for interacting with the Wise Old Man API.

    This service provides a clean abstraction over the wom library,
    handling client lifecycle, error management, and result processing.
    """

    def __init__(self, api_key: str, user_agent: str = "IronForged"):
        """Initialize the WOM service.

        Args:
            api_key: WiseOldMan API key
            user_agent: User agent string for API requests
        """
        self.api_key = api_key
        self.user_agent = user_agent
        self._client: Optional[wom.Client] = None

    async def _get_client(self) -> wom.Client:
        """Get or create a WOM client instance."""
        if self._client is None:
            self._client = wom.Client(api_key=self.api_key, user_agent=self.user_agent)
            await self._client.start()
        return self._client

    def _categorize_error(self, error_msg: str) -> ErrorType:
        """Categorize error based on error message."""
        error_lower = error_msg.lower()

        if "json is malformed" in error_msg or "invalid character" in error_msg:
            return ErrorType.JSON_MALFORMED
        elif "rate limit" in error_lower:
            return ErrorType.RATE_LIMIT
        elif "timeout" in error_lower or "connection" in error_lower:
            return ErrorType.CONNECTION
        else:
            return ErrorType.UNKNOWN

    def _get_retry_delay(self, error_type: ErrorType, attempt: int) -> float:
        """Get retry delay based on error type and attempt number."""
        if error_type == ErrorType.JSON_MALFORMED:
            return 1.0 * (2 ** attempt)
        elif error_type == ErrorType.RATE_LIMIT:
            return 5.0 * (attempt + 1)
        elif error_type == ErrorType.CONNECTION:
            return 2.0 * (attempt + 1)
        else:
            return 0.0

    def _should_retry(self, error_type: ErrorType) -> bool:
        """Determine if error type should be retried."""
        return error_type != ErrorType.UNKNOWN

    async def _execute_with_retry(self, operation, operation_name: str, retries: int = 3, **kwargs):
        """Execute an operation with standardized retry logic."""
        for attempt in range(retries + 1):
            try:
                result = await operation(**kwargs)

                if result.is_ok:
                    return result.unwrap()
                else:
                    error_msg = f"Error in {operation_name}: {result.unwrap_err()}"
                    logger.error(error_msg)
                    raise WomServiceError(error_msg)

            except Exception as e:
                error_msg = str(e)
                error_type = self._categorize_error(error_msg)
                is_last_attempt = attempt == retries

                if is_last_attempt:
                    logger.error(f"{operation_name} error (final attempt): {e}")
                else:
                    logger.warning(f"{operation_name} error (attempt {attempt + 1}/{retries + 1}): {e}")

                if not self._should_retry(error_type) or is_last_attempt:
                    if error_type == ErrorType.JSON_MALFORMED:
                        raise WomServiceError(
                            "WOM API returned invalid data format. The service may be temporarily unavailable.",
                            error_type
                        )
                    elif error_type == ErrorType.RATE_LIMIT:
                        raise WomServiceError(
                            "WOM API rate limit exceeded. Please try again later.",
                            error_type
                        )
                    elif error_type == ErrorType.CONNECTION:
                        raise WomServiceError(
                            "WOM API connection timeout. Please check your internet connection and try again.",
                            error_type
                        )
                    else:
                        raise WomServiceError(f"Failed {operation_name}: {e}", error_type)

                wait_time = self._get_retry_delay(error_type, attempt)
                if wait_time > 0:
                    logger.info(f"Retrying {operation_name} after {wait_time}s...")
                    await asyncio.sleep(wait_time)

        raise WomServiceError(f"Unexpected error in {operation_name} retry logic")

    async def close(self):
        """Close the WOM client connection."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning(f"Error closing WOM client: {e}")
            finally:
                self._client = None

    async def get_group_details(self, group_id: int, retries: int = 2) -> GroupDetail:
        """Get group details from WOM.

        Args:
            group_id: WiseOldMan group ID
            retries: Number of retry attempts for transient errors

        Returns:
            GroupDetail object containing group information

        Raises:
            WomServiceError: If the API call fails or returns an error
        """
        client = await self._get_client()

        async def operation(group_id):
            return await client.groups.get_details(group_id)

        return await self._execute_with_retry(
            operation, "get_group_details", retries, group_id=group_id
        )

    async def get_group_gains(
        self,
        group_id: int,
        metric: Metric = Metric.Overall,
        period: Period = Period.Month,
        limit: int = 50,
        offset: int = 0,
        retries: int = 3,
    ) -> List[GroupMemberGains]:
        """Get group member gains from WOM.

        Args:
            group_id: WiseOldMan group ID
            metric: Metric to fetch gains for (default: Overall)
            period: Time period for gains (default: Month)
            limit: Number of records to fetch (default: 50)
            offset: Offset for pagination (default: 0)
            retries: Number of retry attempts for transient errors

        Returns:
            List of GroupMemberGains objects

        Raises:
            WomServiceError: If the API call fails or returns an error
        """
        client = await self._get_client()

        async def operation(group_id, metric, period, limit, offset):
            return await client.groups.get_gains(
                group_id, metric=metric, period=period, limit=limit, offset=offset
            )

        return await self._execute_with_retry(
            operation, f"get_group_gains at offset {offset}", retries,
            group_id=group_id, metric=metric, period=period, limit=limit, offset=offset
        )

    async def get_all_group_gains(
        self,
        group_id: int,
        metric: Metric = Metric.Overall,
        period: Period = Period.Month,
        limit: int = 50,
        max_iterations: int = 100,
    ) -> List[GroupMemberGains]:
        """Get all group member gains, handling pagination automatically.

        Args:
            group_id: WiseOldMan group ID
            metric: Metric to fetch gains for (default: Overall)
            period: Time period for gains (default: Month)
            limit: Number of records to fetch per page (default: 50)
            max_iterations: Maximum number of pagination requests (default: 100)

        Returns:
            List of all GroupMemberGains objects

        Raises:
            WomServiceError: If any API call fails or returns an error
        """
        all_gains = []
        offset = 0
        iterations = 0

        while iterations < max_iterations:
            gains = await self.get_group_gains(
                group_id=group_id,
                metric=metric,
                period=period,
                limit=limit,
                offset=offset,
            )

            if not gains:
                logger.info("Received empty gains response, ending pagination")
                break

            all_gains.extend(gains)

            if len(gains) < limit:
                break

            offset += limit
            iterations += 1

            if iterations % 5 == 0 and iterations > 0:
                logger.debug(
                    f"Processed {iterations} pagination requests, total gains: {len(all_gains)}"
                )
                await asyncio.sleep(0.1)

        if iterations >= max_iterations:
            logger.warning(
                f"Pagination safety limit reached ({max_iterations} iterations), may have incomplete data"
            )

        logger.info(
            f"Retrieved {len(all_gains)} total gains across {iterations} requests"
        )
        return all_gains

    async def get_group_members_with_roles(
        self, group_id: int, ignored_roles: Optional[List[GroupRole]] = None
    ) -> Tuple[List[str], List[str]]:
        """Get group members, filtering by roles and returning ignored members separately.

        Args:
            group_id: WiseOldMan group ID
            ignored_roles: List of roles to ignore (default: None)

        Returns:
            Tuple of (valid_members, ignored_members) username lists

        Raises:
            WomServiceError: If the API call fails or returns an error
        """
        if ignored_roles is None:
            ignored_roles = []

        group_details = await self.get_group_details(group_id)

        valid_members = []
        ignored_members = []

        for membership in group_details.memberships:
            username = membership.player.username
            member_role = membership.role

            if member_role is None:
                logger.info(f"{username} has no role, skipping.")
                continue

            if member_role in ignored_roles:
                logger.info(
                    f"{username} has ignored role {member_role}, adding to ignored list."
                )
                ignored_members.append(username)
            else:
                valid_members.append(username)

        return valid_members, ignored_members

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        try:
            await self.close()
        except Exception as e:
            logger.warning(f"Error during WOM service cleanup: {e}")
        finally:
            self._client = None


class WomServiceManager:
    """Manager for WOM service instances with proper lifecycle management."""

    def __init__(self):
        self._instance: Optional[WomService] = None
        self._api_key: Optional[str] = None

    def initialize(self, api_key: str, user_agent: str = "IronForged") -> WomService:
        """Initialize the WOM service with given credentials.

        Args:
            api_key: WiseOldMan API key
            user_agent: User agent string for API requests

        Returns:
            WomService instance
        """
        if self._instance is not None:
            asyncio.create_task(self._instance.close())

        self._api_key = api_key
        self._instance = WomService(api_key, user_agent)
        return self._instance

    def get_service(self) -> WomService:
        """Get the current WOM service instance.

        Returns:
            WomService instance

        Raises:
            ValueError: If service not initialized
        """
        if self._instance is None:
            raise ValueError("WOM service not initialized. Call initialize() first.")
        return self._instance

    async def close(self):
        """Close the current WOM service instance."""
        if self._instance is not None:
            await self._instance.close()
            self._instance = None
            self._api_key = None

    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._instance is not None


_wom_manager = WomServiceManager()


def get_wom_service(api_key: str = None) -> WomService:
    """Get the WOM service instance.

    Args:
        api_key: WiseOldMan API key (required if not already initialized)

    Returns:
        WomService instance

    Raises:
        ValueError: If no API key provided and service not initialized
    """
    if not _wom_manager.is_initialized():
        if api_key is None:
            raise ValueError("API key required for first WOM service initialization")
        return _wom_manager.initialize(api_key)

    return _wom_manager.get_service()


def reset_wom_service():
    """Reset the WOM service (useful for testing)."""
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(_wom_manager.close())
    except RuntimeError:
        # No event loop running, do synchronous cleanup
        if _wom_manager._instance is not None:
            _wom_manager._instance = None
            _wom_manager._api_key = None