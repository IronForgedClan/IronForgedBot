from datetime import datetime, timezone
from enum import IntEnum
from sqlalchemy import ForeignKey, Integer, String, Enum
from sqlalchemy.orm import Mapped, mapped_column

from ironforgedbot.database.database import Base
from ironforgedbot.models.decorators import UTCDateTime


class ChangeType(IntEnum):
    ADD_MEMBER = 0
    NAME_CHANGE = 1
    ACTIVITY_CHANGE = 2
    JOINED_DATE_CHANGE = 3
    RESET_INGOTS = 4
    ADD_INGOTS = 5
    REMOVE_INGOTS = 6
    RANK_CHANGE = 7
    PURCHASE_RAFFLE_TICKETS = 8


class Changelog(Base):
    __tablename__ = "changelog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[str] = mapped_column(
        String(length=36), ForeignKey(column="members.id"), nullable=False
    )
    admin_id: Mapped[str] = mapped_column(
        String(length=36), ForeignKey(column="members.id"), nullable=True
    )
    change_type: Mapped[ChangeType] = mapped_column(
        Enum(ChangeType, native_enum=False), nullable=False
    )
    previous_value: Mapped[str] = mapped_column(String(length=255), nullable=True)
    new_value: Mapped[str] = mapped_column(String(length=255), nullable=True)
    comment: Mapped[str] = mapped_column(String(length=255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(tz=timezone.utc)
    )
