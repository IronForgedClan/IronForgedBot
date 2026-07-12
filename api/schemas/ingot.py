from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from ironforgedbot.models import Changelog


class IngotTransaction(BaseModel):
    id: int
    change_type: str
    previous_value: str
    new_value: str
    comment: str | None = None
    admin_name: str | None = None
    timestamp: datetime

    @classmethod
    def from_changelog(cls, log: Changelog) -> "IngotTransaction":
        return cls(
            id=log.id,
            change_type=(
                log.change_type.name
                if isinstance(log.change_type, Enum)
                else str(log.change_type)
            ),
            previous_value=log.previous_value or "",
            new_value=log.new_value or "",
            comment=log.comment,
            admin_name=None,
            timestamp=log.timestamp,
        )


class IngotBalance(BaseModel):
    discord_id: int
    nickname: str
    ingots: int


class IngotTransactionsResponse(BaseModel):
    discord_id: int
    transactions: list[IngotTransaction]
