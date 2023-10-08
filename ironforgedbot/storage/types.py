from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Optional

class StorageError(Exception):
    """Base exception raised for storage operations."""

@dataclass
class Member:
    """A stored Discord member."""
    id: int
    runescape_name: str
    ingots: int = 0

    def __str__(self):
        return f'Member: (ID: {self.id}, RSN: {self.runescape_name}, Ingots: {self.ingots})'


class IngotsStorage(type):
    """Metaclass for interacting with ingots storage.

    IronForged storage is best described as a single table:
    Discord ID (key), runescape name, ingot count

    Operations are based on player runescape names, but these
    are malleable and will often change. Inversely, the Discord
    id never changes.
"""

    @abstractmethod
    def read_member(self, player: str) -> Optional[Member]:
        """Read member by runescape name."""

    @abstractmethod
    def read_members(self) -> List[Member]:
        """Read members from storage."""

    @abstractmethod
    def add_members(self, members: List[Member], attribution: str, note: str = '') -> None:
        """Adds new members to storage."""

    @abstractmethod
    def update_members(self, members: List[Member], attribution: str, note: str = '') -> None:
        """Updates metadata for the provided members."""

    @abstractmethod
    def remove_members(self, members: List[Member], attribution: str, note: str = '') -> None:
        """Removes provided members from storage. Requires Member.id."""
