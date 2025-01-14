from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


class StorageError(Exception):
    """Base exception raised for storage operations."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


@dataclass
class Member:
    """A stored Discord member."""

    id: int
    runescape_name: str
    ingots: int = 0
    joined_date: datetime | str = "unknown"

    def __str__(self):
        return (
            f"Member: (ID: {self.id}, RSN: {self.runescape_name}, "
            f"Ingots: {self.ingots}, Joined: {str(self.joined_date)})"
        )


class IngotsStorage(type):
    """Metaclass for interacting with ingots storage.

    IronForged storage is best described as a single table:
    Discord ID (key), runescape name, ingot count

    Operations are based on player runescape names, but these
    are malleable and will often change. Inversely, the Discord
    id never changes.

    For raffles, a separate table controls the existence of a raffle.
    Only one raffle can be ongoing at a time. For the table controlling
    how many tickets a given member has, the effective schema is:
    Discord ID (key), ticket count.

    The ingots table acts as the RSN:ID mapping.

    Implementation note: Ideally, ticket count would just be another
    column on the existing ingots table, and we could cut out the
    raffle functions from the interface. However, with sheets as the
    primary storage system, that interface is clunky enough that it is
    more difficult to update individual columns.
    """

    @abstractmethod
    def read_member(self, player: str) -> Optional[Member]:
        """Read member by runescape name."""

    @abstractmethod
    def read_members(self) -> List[Member]:
        """Read members from storage."""

    @abstractmethod
    def add_members(
        self, members: List[Member], attribution: str, note: str = ""
    ) -> None:
        """Adds new members to storage."""

    @abstractmethod
    def update_members(
        self, members: List[Member], attribution: str, note: str = ""
    ) -> None:
        """Updates metadata for the provided members."""

    @abstractmethod
    def remove_members(
        self, members: List[Member], attribution: str, note: str = ""
    ) -> None:
        """Removes provided members from storage. Requires Member.id."""

    @abstractmethod
    def read_raffle(self) -> bool:
        """Reads if a raffle is currently ongoing."""

    @abstractmethod
    def start_raffle(self, attribution: str) -> None:
        """Starts a raffle, enabling purchase of raffle tickets."""

    @abstractmethod
    def end_raffle(self, attribution: str) -> None:
        """Marks a raffle as over, disallowing purchase of tickets."""

    @abstractmethod
    def read_raffle_tickets(self) -> Dict[int, int]:
        """Reads number of tickets a user has for the current raffle.

        Returns:
            Dictionary of Discord ID:Number of tickets.
        """

    @abstractmethod
    def add_raffle_tickets(self, member_id: int, tickets: int) -> None:
        """Adds tickets to a given member.

        Args:
            member_id: Discord ID of user to add tickets to.
            tickets: Number of tickets to add to this user.
        """

    @abstractmethod
    def delete_raffle_tickets(self, attribution: str) -> None:
        """Deletes all current raffle tickets. Called once when ending a raffle."""

    @abstractmethod
    def get_absentees(self) -> dict[str:str]:
        """Returns known list of absentees with <rsn:date> format"""

    @abstractmethod
    def shutdown(self) -> None:
        """Closes open connections"""
