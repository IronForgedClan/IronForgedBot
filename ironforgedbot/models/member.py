import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from ironforgedbot.common.ranks import RANK
from ironforgedbot.database.database import Base
from ironforgedbot.models.decorators import UTCDateTime


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    discord_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    nickname: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    ingots: Mapped[int] = mapped_column(Integer, default=0)
    rank: Mapped[RANK] = mapped_column(String)
    joined_date: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(timezone.utc)
    )
    last_changed_date: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<Member(id={self.id}, discord_id={self.discord_id}, active={self.active}, nickname={self.nickname}, ingots={self.ingots}, rank={self.rank}, joined_date={self.joined_date}, last_changed_date={self.last_changed_date})>"
