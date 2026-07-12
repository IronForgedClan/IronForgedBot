from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from api.schemas.member import MemberRef
from ironforgedbot.models import Changelog, Member


class IngotTransaction(BaseModel):
    id: int
    change_type: str
    previous_value: str
    new_value: str
    comment: str | None = None
    admin: MemberRef | None = None
    timestamp: datetime

    @classmethod
    def from_changelog(
        cls, log: Changelog, admin_member: Member | None
    ) -> "IngotTransaction":
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
            admin=MemberRef.from_member(admin_member) if admin_member else None,
            timestamp=log.timestamp,
        )


class IngotBalance(BaseModel):
    nickname: str
    ingots: int


class IngotTransactionsResponse(BaseModel):
    transactions: list[IngotTransaction]
