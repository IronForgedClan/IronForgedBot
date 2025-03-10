import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from ironforgedbot.common.ranks import RANK
from ironforgedbot.database.database import Base


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
    joined_date: Mapped[datetime] = mapped_column(DateTime)
    last_changed_date: Mapped[datetime] = mapped_column(DateTime)
