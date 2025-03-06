from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ironforgedbot.database.database import Base


class ChangeType(Enum):
    NAME_CHANGE = 1
    ACTIVE_CHANGE = 2
    ADD_INGOTS = 3
    REMOVE_INGOTS = 4
    RANK_CHANGE = 5


class Changelog(Base):
    __tablename__ = "changelog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    admin_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    change_type: Mapped[ChangeType] = mapped_column(Integer)
    previous_value: Mapped[str] = mapped_column(String)
    new_value: Mapped[str] = mapped_column(String)
    note: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
