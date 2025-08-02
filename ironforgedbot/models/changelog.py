from datetime import datetime, timezone
from enum import IntEnum
from sqlalchemy import ForeignKey, Integer, String, Enum
from sqlalchemy.orm import Mapped, mapped_column

from ironforgedbot.database.database import Base
from ironforgedbot.models.decorators import UTCDateTime


class ChangeType(Enum):
    ADD_MEMBER
    NAME_CHANGE
    ACTIVITY_CHANGE
    JOINED_DATE_CHANGE
    RESET_INGOTS
    ADD_INGOTS
    REMOVE_INGOTS
    RANK_CHANGE
    PURCHASE_RAFFLE_TICKETS


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
