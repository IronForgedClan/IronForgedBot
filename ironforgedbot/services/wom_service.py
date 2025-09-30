import asyncio
import logging
from typing import List, Optional, Tuple

import wom
from wom import Metric, Period
from wom.models import GroupDetail, GroupMemberGains, NameChange

from ironforgedbot.config import CONFIG

logger = logging.getLogger(__name__)


class WomServiceError(Exception):
    """Base exception for WOM service operations."""

    pass


class WomRateLimitError(WomServiceError):
    """Exception raised when WOM API rate limit is exceeded."""

    pass


class WomTimeoutError(WomServiceError):
    """Exception raised when WOM API requests timeout."""

    pass


class WomService:
    """Simplified WOM service for business operations.

    Provides a clean interface for WOM API operations needed by the bot.
    Follows established service patterns with proper resource management.
    """

    def __init__(self):
        """Initialize the WOM service with application configuration."""
        if not CONFIG.WOM_API_KEY:
            raise WomServiceError("WOM_API_KEY not configured")

        self.api_key = CONFIG.WOM_API_KEY
        self.group_id = CONFIG.WOM_GROUP_ID
        self._client: Optional[wom.Client] = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.close()

    async def _get_client(self) -> wom.Client:
        """Get or create a WOM client instance."""
        if self._client is None:
            self._client = wom.Client(api_key=self.api_key, user_agent="IronForged")
            await self._client.start()
        return self._client

    async def close(self):
        """Close the WOM client connection."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning(f"Error closing WOM client: {e}")
            finally:
                self._client = None

    async def get_monthly_activity_data(
        self, group_id: Optional[int] = None
    ) -> Tuple[GroupDetail, List[GroupMemberGains]]:
        """Get group details and monthly member gains for activity checking.

        Args:
            group_id: WiseOldMan group ID (defaults to configured group)

        Returns:
            Tuple of (group_details, monthly_member_gains)

        Raises:
            WomServiceError: If the API call fails
            WomRateLimitError: If rate limit is exceeded
            WomTimeoutError: If request times out
        """
        if group_id is None:
            group_id = self.group_id

        client = await self._get_client()

        try:
            # Get group details
            logger.debug(f"Fetching group details for group {group_id}")
            group_details = await asyncio.wait_for(
                self._get_group_details(client, group_id), timeout=30.0
            )

            # Get monthly member gains with pagination
            logger.debug(f"Fetching monthly gains for group {group_id}")
            member_gains = await asyncio.wait_for(
                self._get_all_group_gains(client, group_id), timeout=120.0
            )

            logger.info(
                f"Retrieved activity data: {len(group_details.memberships)} members, {len(member_gains)} gains"
            )
            return group_details, member_gains

        except asyncio.TimeoutError as e:
            logger.error(f"Timeout getting activity data for group {group_id}: {e}")
            raise WomTimeoutError("WOM API request timed out")
        except Exception as e:
            logger.error(f"Error getting activity data for group {group_id}: {e}")
            self._handle_wom_error(e)

    async def get_group_membership_data(
        self, group_id: Optional[int] = None
    ) -> GroupDetail:
        """Get group membership data for discrepancy checking.

        Args:
            group_id: WiseOldMan group ID (defaults to configured group)

        Returns:
            Group details with membership information

        Raises:
            WomServiceError: If the API call fails
            WomRateLimitError: If rate limit is exceeded
            WomTimeoutError: If request times out
        """
        if group_id is None:
            group_id = self.group_id

        client = await self._get_client()

        try:
            logger.debug(f"Fetching membership data for group {group_id}")
            group_details = await asyncio.wait_for(
                self._get_group_details(client, group_id), timeout=30.0
            )

            logger.info(
                f"Retrieved membership data: {len(group_details.memberships)} members"
            )
            return group_details

        except asyncio.TimeoutError as e:
            logger.error(f"Timeout getting membership data for group {group_id}: {e}")
            raise WomTimeoutError("WOM API request timed out")
        except Exception as e:
            logger.error(f"Error getting membership data for group {group_id}: {e}")
            self._handle_wom_error(e)

    async def get_player_name_history(self, player_name: str) -> List[NameChange]:
        """Get player's RuneScape name change history.

        Args:
            player_name: RuneScape username

        Returns:
            List of name changes

        Raises:
            WomServiceError: If the API call fails
            WomRateLimitError: If rate limit is exceeded
            WomTimeoutError: If request times out
        """
        client = await self._get_client()

        try:
            logger.debug(f"Fetching name history for player {player_name}")
            result = await asyncio.wait_for(
                client.players.get_name_changes(player_name), timeout=30.0
            )

            if result.is_err:
                error_details = result.unwrap_err()
                logger.error(
                    f"WOM API error getting name history for {player_name}: {error_details}"
                )
                raise WomServiceError(f"Failed to get name history: {error_details}")

            name_changes = result.unwrap()
            logger.info(
                f"Retrieved name history for {player_name}: {len(name_changes)} changes"
            )
            return name_changes

        except asyncio.TimeoutError as e:
            logger.error(f"Timeout getting name history for {player_name}: {e}")
            raise WomTimeoutError("WOM API request timed out")
        except (WomServiceError, WomRateLimitError, WomTimeoutError):
            # Re-raise our custom exceptions without modification
            raise
        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Error getting name history for {player_name}: {type(e).__name__}: {e}")
            if any(keyword in error_str for keyword in ['json', 'decode', 'parse', 'invalid']):
                logger.error(f"Detected JSON parsing error for {player_name}, WOM API may have returned HTML instead of JSON")
            self._handle_wom_error(e)

    async def _get_group_details(
        self, client: wom.Client, group_id: int
    ) -> GroupDetail:
        """Get group details with error handling."""
        try:
            logger.debug(f"Fetching group details for group {group_id}")
            result = await client.groups.get_details(group_id)

            if result.is_ok:
                return result.unwrap()
            else:
                error_details = result.unwrap_err()
                logger.error(f"WOM API error getting group details: {error_details}")
                raise WomServiceError(f"WOM API error: {error_details}")

        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Unexpected error getting group details: {type(e).__name__}: {e}")
            if any(keyword in error_str for keyword in ['json', 'decode', 'parse', 'invalid']):
                logger.error("Detected JSON parsing error, WOM API may have returned HTML instead of JSON")
            raise

    async def _get_all_group_gains(
        self, client: wom.Client, group_id: int
    ) -> List[GroupMemberGains]:
        """Get all group member gains with pagination."""
        all_gains = []
        limit = 50
        offset = 0
        page = 0
        max_pages = 100

        logger.debug("Starting to fetch group gains with pagination")

        while page < max_pages:
            # Retry logic for transient errors
            max_retries = 2  # Reduced from 3 to minimize delay accumulation
            retry_delay = 1.0

            for attempt in range(max_retries):
                try:
                    logger.debug(f"Fetching gains page {page + 1}, offset={offset}, limit={limit} (attempt {attempt + 1})")

                    # Remove nested timeout - rely on outer timeout for entire operation
                    result = await client.groups.get_gains(
                        group_id,
                        metric=Metric.Overall,
                        period=Period.Month,
                        limit=limit,
                        offset=offset,
                    )

                    if result.is_ok:
                        gains = result.unwrap()
                        logger.debug(f"Page {page + 1}: successfully retrieved {len(gains)} gains")
                        break  # Success, exit retry loop
                    else:
                        error_details = result.unwrap_err()
                        logger.error(f"WOM API error getting group gains page {page + 1}: {error_details}")

                        # Check if this is a transient error that we should retry
                        error_str = str(error_details).lower()
                        if attempt < max_retries - 1 and any(keyword in error_str for keyword in ['timeout', 'rate limit', 'server error', '502', '503', '504']):
                            logger.warning(f"Transient error on page {page + 1}, attempt {attempt + 1}, retrying in {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                        else:
                            raise WomServiceError(f"WOM API error: {error_details}")

                except Exception as e:
                    error_str = str(e).lower()
                    logger.error(f"Unexpected error fetching gains page {page + 1}, attempt {attempt + 1}: {type(e).__name__}: {e}")

                    # Check if this looks like a JSON parsing error or other transient issue
                    is_json_error = any(keyword in error_str for keyword in ['json', 'decode', 'parse', 'invalid'])
                    is_connection_error = any(keyword in error_str for keyword in ['connection', 'network', 'timeout'])

                    if is_json_error:
                        logger.error(f"Detected JSON parsing error on page {page + 1}, this may indicate WOM API returned HTML instead of JSON")

                    # Retry for certain types of errors
                    if attempt < max_retries - 1 and (is_json_error or is_connection_error):
                        logger.warning(f"Retrying page {page + 1} due to transient error in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        raise

            if not gains:
                logger.debug(f"Page {page + 1}: no gains returned, ending pagination")
                break

            all_gains.extend(gains)

            # If we got fewer results than the limit, we've reached the end
            if len(gains) < limit:
                logger.debug(f"Page {page + 1}: received {len(gains)} gains (less than limit {limit}), ending pagination")
                break

            offset += limit
            page += 1

            # Small delay between all requests to be respectful to the API
            await asyncio.sleep(0.1)

        if page >= max_pages:
            logger.warning(
                f"Reached max pages limit ({max_pages}), may have incomplete data"
            )

        logger.info(f"Retrieved {len(all_gains)} total gains across {page + 1} pages")
        return all_gains

    def _handle_wom_error(self, error: Exception):
        """Convert WOM errors to appropriate service exceptions."""
        error_str = str(error).lower()

        if "rate limit" in error_str:
            logger.error(f"WOM API rate limit exceeded: {error}")
            raise WomRateLimitError("WOM API rate limit exceeded")
        elif "timeout" in error_str or "connection" in error_str:
            logger.error(f"WOM API connection timeout: {error}")
            raise WomTimeoutError("WOM API connection timeout")
        else:
            logger.error(f"WOM API error: {error}")
            raise WomServiceError("WOM API error occurred")


def get_wom_service() -> WomService:
    """Create a configured WOM service instance.

    Returns:
        WomService instance configured with application settings

    Raises:
        WomServiceError: If configuration is missing or invalid
    """
    return WomService()
