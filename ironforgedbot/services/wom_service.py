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
            logger.error(f"Error getting name history for {player_name}: {e}")
            self._handle_wom_error(e)

    async def _get_group_details(
        self, client: wom.Client, group_id: int
    ) -> GroupDetail:
        """Get group details."""
        result = await client.groups.get_details(group_id)

        if result.is_ok:
            return result.unwrap()
        else:
            error_details = result.unwrap_err()
            logger.error(f"WOM API error getting group details: {error_details}")
            raise WomServiceError(f"WOM API error: {error_details}")

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
            result = await client.groups.get_gains(
                group_id,
                metric=Metric.Overall,
                period=Period.Month,
                limit=limit,
                offset=offset,
            )

            if result.is_ok:
                gains = result.unwrap()
            else:
                error_details = result.unwrap_err()
                logger.error(f"WOM API error getting group gains: {error_details}")
                raise WomServiceError(f"WOM API error: {error_details}")

            logger.debug(f"Page {page + 1}: retrieved {len(gains)} gains")

            if not gains:
                break

            all_gains.extend(gains)

            # If we got fewer results than the limit, we've reached the end
            if len(gains) < limit:
                break

            offset += limit
            page += 1

            # Small delay every 5 pages to be respectful to the API
            if page % 5 == 0:
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
