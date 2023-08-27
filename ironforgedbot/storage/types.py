from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

class StorageError(Exception):
    """Base exception raised for storage operations."""

@dataclass
class Member:
    """A stored Discord member."""
    id: int
    runescape_name: str


class IngotsStorage(ABC):
    """Metaclass for interacting with ingots storage.

    IronForged storage is best described as two tables:
    Discord id -> runescape name.
    runescape name -> ingot count.

    Operations are based on player runescape names, but these
    are malleable and will often change. Inversely, the Discord
    id never changes.

    caller is plumbed through for mutation calls for attribution
    logging.
"""

    @abstractmethod
    def read_ingots(self, player: str) -> int:
        """Read ingots from storage for player."""

    @abstractmethod
    def adjust_ingots(self, player: str, ingots: int, caller: str) -> None:
        """Adjust ingot count by given amount."""

    @abstractmethod
    def update_ingots(self, player: str, ingots: int, caller: str) -> None:
        """Overwrite ingot count for player with new value."""

    @abstractmethod
    def read_members(self) -> List[Member]:
        """Read members from storage."""

    @abstractmethod
    def add_members(self, members: List[Member], caller: str) -> None:
        """Adds new members to storage."""

    @abstractmethod
    def update_members(self, members: List[Member], caller: str) -> None:
        """Updates metadata for the provided members."""

    @abstractmethod
    def remove_members(self, members: List[Member], caller: str) -> None:
        """Removes provided members from storage. Requires Member.id."""
