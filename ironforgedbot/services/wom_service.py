import logging
from typing import List, Optional, Tuple

import wom
from wom import GroupRole, Metric, Period
from wom.models import GroupDetail, GroupMembership, GroupMemberGains

logger = logging.getLogger(__name__)


class WomServiceError(Exception):
    """Exception raised for WOM service operations."""
    pass


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

    async def close(self):
        """Close the WOM client connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def get_group_details(self, group_id: int) -> GroupDetail:
        """Get group details from WOM.
        
        Args:
            group_id: WiseOldMan group ID
            
        Returns:
            GroupDetail object containing group information
            
        Raises:
            WomServiceError: If the API call fails or returns an error
        """
        client = await self._get_client()
        
        try:
            result = await client.groups.get_details(group_id)
        except Exception as e:
            logger.error(f"WOM API error fetching group details: {e}")
            raise WomServiceError(f"Failed to fetch group details: {e}")

        if not result.is_ok:
            error_msg = f"Error fetching WOM group: {result.unwrap_err()}"
            logger.error(error_msg)
            raise WomServiceError(error_msg)

        return result.unwrap()

    async def get_group_gains(
        self,
        group_id: int,
        metric: Metric = Metric.Overall,
        period: Period = Period.Month,
        limit: int = 50,
        offset: int = 0,
    ) -> List[GroupMemberGains]:
        """Get group member gains from WOM.
        
        Args:
            group_id: WiseOldMan group ID
            metric: Metric to fetch gains for (default: Overall)
            period: Time period for gains (default: Month)
            limit: Number of records to fetch (default: 50)
            offset: Offset for pagination (default: 0)
            
        Returns:
            List of GroupMemberGains objects
            
        Raises:
            WomServiceError: If the API call fails or returns an error
        """
        client = await self._get_client()
        
        try:
            result = await client.groups.get_gains(
                group_id,
                metric=metric,
                period=period,
                limit=limit,
                offset=offset,
            )
        except Exception as e:
            logger.error(f"WOM API error fetching gains at offset {offset}: {e}")
            raise WomServiceError(f"Failed to fetch group gains: {e}")

        if not result.is_ok:
            error_msg = f"Error fetching gains from WOM: {result.unwrap_err()}"
            logger.error(error_msg)
            raise WomServiceError(error_msg)

        return result.unwrap()

    async def get_all_group_gains(
        self,
        group_id: int,
        metric: Metric = Metric.Overall,
        period: Period = Period.Month,
        limit: int = 50,
    ) -> List[GroupMemberGains]:
        """Get all group member gains, handling pagination automatically.
        
        Args:
            group_id: WiseOldMan group ID
            metric: Metric to fetch gains for (default: Overall)
            period: Time period for gains (default: Month)
            limit: Number of records to fetch per page (default: 50)
            
        Returns:
            List of all GroupMemberGains objects
            
        Raises:
            WomServiceError: If any API call fails or returns an error
        """
        all_gains = []
        offset = 0
        
        while True:
            gains = await self.get_group_gains(
                group_id=group_id,
                metric=metric,
                period=period,
                limit=limit,
                offset=offset,
            )
            
            all_gains.extend(gains)
            
            # If we got fewer results than the limit, we've reached the end
            if len(gains) < limit:
                break
                
            offset += limit
        
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
                logger.info(f"{username} has ignored role {member_role}, adding to ignored list.")
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


# Global singleton instance for the WOM service
_wom_service_instance: Optional[WomService] = None


def get_wom_service(api_key: str = None) -> WomService:
    """Get the global WOM service instance.
    
    Args:
        api_key: WiseOldMan API key (required for first call)
        
    Returns:
        WomService instance
        
    Raises:
        ValueError: If no API key provided and service not initialized
    """
    global _wom_service_instance
    
    if _wom_service_instance is None:
        if api_key is None:
            raise ValueError("API key required for first WOM service initialization")
        _wom_service_instance = WomService(api_key)
    
    return _wom_service_instance


def reset_wom_service():
    """Reset the WOM service singleton (useful for testing)."""
    global _wom_service_instance
    _wom_service_instance = None