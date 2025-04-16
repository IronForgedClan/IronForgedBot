from datetime import datetime, timezone
from enum import StrEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ironforgedbot.database.database import Base
from ironforgedbot.models.decorators import UTCDateTime


class ChangeType(StrEnum):
    ADD_MEMBER = "add"
    NAME_CHANGE = "name_change"
    ACTIVITY_CHANGE = "activity_change"
    JOINED_DATE_CHANGE = "joined_date_change"
    RESET_INGOTS = "reset_ingots"
    ADD_INGOTS = "add_ingots"
    REMOVE_INGOTS = "remove_ingots"
    RANK_CHANGE = "rank_change"
    PURCHASE_RAFFLE_TICKETS = "purchase_raffle_tickets"


class Changelog(Base):
    __tablename__ = "changelog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), nullable=False)
    admin_id: Mapped[str] = mapped_column(ForeignKey("members.id"), nullable=True)
    change_type: Mapped[ChangeType] = mapped_column(String, nullable=False)
    previous_value: Mapped[str] = mapped_column(String, nullable=True)
    new_value: Mapped[str] = mapped_column(String, nullable=True)
    comment: Mapped[str] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(timezone.utc)
    )
