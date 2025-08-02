from datetime import datetime, timezone
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from ironforgedbot.database.database import Base
from ironforgedbot.models.decorators import UTCDateTime


class RaffleTicket(Base):
    __tablename__ = "raffle_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[str] = mapped_column(
        String(length=36), ForeignKey(column="members.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    last_changed_date: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(tz=timezone.utc)
    )
