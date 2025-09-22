import asyncio
import logging
from typing import List, Optional

import wom
from wom import GroupRole, Metric, Period
from wom.models import GroupDetail, GroupMemberGains

from ironforgedbot.config import CONFIG

logger = logging.getLogger(__name__)


class WomServiceError(Exception):
    """Exception raised for WOM service operations."""
    pass


class WomClient:
    """Simple client for interacting with the Wise Old Man API.

    Handles configuration automatically and provides a clean interface
    for the WOM operations needed by the application.
    """

    def __init__(self):
        """Initialize the WOM client with application configuration."""
        if not CONFIG.WOM_API_KEY:
            raise WomServiceError("WOM_API_KEY not configured")

        self.api_key = CONFIG.WOM_API_KEY
        self.group_id = CONFIG.WOM_GROUP_ID
        self._client: Optional[wom.Client] = None

    async def _get_client(self) -> wom.Client:
        """Get or create a WOM client instance."""
        if self._client is None:
            self._client = wom.Client(
                api_key=self.api_key,
                user_agent="IronForged"
            )
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

    async def get_group_details(self, group_id: Optional[int] = None) -> GroupDetail:
        """Get group details from WOM.

        Args:
            group_id: WiseOldMan group ID (defaults to configured group)

        Returns:
            GroupDetail object containing group information

        Raises:
            WomServiceError: If the API call fails
        """
        if group_id is None:
            group_id = self.group_id

        client = await self._get_client()

        # Simple retry logic - 2 attempts with 1 second delay
        for attempt in range(2):
            try:
                result = await client.groups.get_details(group_id)

                if result.is_ok:
                    return result.unwrap()
                else:
                    error_msg = f"WOM API error: {result.unwrap_err()}"
                    if attempt == 0:
                        logger.warning(f"{error_msg}, retrying...")
                        await asyncio.sleep(1.0)
                        continue
                    else:
                        raise WomServiceError(error_msg)

            except Exception as e:
                error_str = str(e).lower()
                if attempt == 0 and ("timeout" in error_str or "connection" in error_str):
                    logger.warning(f"Connection error: {e}, retrying...")
                    await asyncio.sleep(1.0)
                    continue
                else:
                    raise WomServiceError(f"Failed to get group details: {e}")

    async def get_group_gains(
        self,
        group_id: Optional[int] = None,
        metric: Metric = Metric.Overall,
        period: Period = Period.Month,
        limit: int = 50,
        offset: int = 0,
    ) -> List[GroupMemberGains]:
        """Get group member gains from WOM.

        Args:
            group_id: WiseOldMan group ID (defaults to configured group)
            metric: Metric to fetch gains for
            period: Time period for gains
            limit: Number of records to fetch
            offset: Offset for pagination

        Returns:
            List of GroupMemberGains objects

        Raises:
            WomServiceError: If the API call fails
        """
        if group_id is None:
            group_id = self.group_id

        client = await self._get_client()

        # Simple retry logic - 2 attempts with 1 second delay
        for attempt in range(2):
            try:
                result = await client.groups.get_gains(
                    group_id,
                    metric=metric,
                    period=period,
                    limit=limit,
                    offset=offset,
                )

                if result.is_ok:
                    return result.unwrap()
                else:
                    error_msg = f"WOM API error: {result.unwrap_err()}"
                    if attempt == 0:
                        logger.warning(f"{error_msg}, retrying...")
                        await asyncio.sleep(1.0)
                        continue
                    else:
                        raise WomServiceError(error_msg)

            except Exception as e:
                error_str = str(e).lower()
                if attempt == 0 and ("timeout" in error_str or "connection" in error_str):
                    logger.warning(f"Connection error: {e}, retrying...")
                    await asyncio.sleep(1.0)
                    continue
                else:
                    raise WomServiceError(f"Failed to get group gains: {e}")

    async def get_all_group_gains(
        self,
        group_id: Optional[int] = None,
        metric: Metric = Metric.Overall,
        period: Period = Period.Month,
        limit: int = 50,
        max_pages: int = 100,
    ) -> List[GroupMemberGains]:
        """Get all group member gains, handling pagination automatically.

        Args:
            group_id: WiseOldMan group ID (defaults to configured group)
            metric: Metric to fetch gains for
            period: Time period for gains
            limit: Number of records to fetch per page
            max_pages: Maximum number of pages to fetch (safety limit)

        Returns:
            List of all GroupMemberGains objects

        Raises:
            WomServiceError: If any API call fails
        """
        all_gains = []
        offset = 0
        page = 0

        while page < max_pages:
            gains = await self.get_group_gains(
                group_id=group_id,
                metric=metric,
                period=period,
                limit=limit,
                offset=offset,
            )

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
            logger.warning(f"Reached max pages limit ({max_pages}), may have incomplete data")

        logger.info(f"Retrieved {len(all_gains)} total gains across {page} pages")
        return all_gains

    async def get_group_members_with_roles(
        self,
        group_id: Optional[int] = None,
        ignored_roles: Optional[List[GroupRole]] = None
    ) -> tuple[List[str], List[str]]:
        """Get group members, filtering by roles.

        Args:
            group_id: WiseOldMan group ID (defaults to configured group)
            ignored_roles: List of roles to ignore

        Returns:
            Tuple of (valid_members, ignored_members) username lists

        Raises:
            WomServiceError: If the API call fails
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
                logger.debug(f"{username} has no role, skipping")
                continue

            if member_role in ignored_roles:
                logger.debug(f"{username} has ignored role {member_role}")
                ignored_members.append(username)
            else:
                valid_members.append(username)

        return valid_members, ignored_members

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.close()


async def get_wom_client() -> WomClient:
    """Create a configured WOM client.

    Returns:
        WomClient instance configured with application settings

    Raises:
        WomServiceError: If configuration is missing or invalid
    """
    return WomClient()