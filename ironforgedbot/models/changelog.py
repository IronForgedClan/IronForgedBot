from datetime import datetime
from enum import StrEnum
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ironforgedbot.database.database import Base


class ChangeType(StrEnum):
    ADD_MEMBER = "add"
    NAME_CHANGE = "name_change"
    ACTIVITY_CHANGE = "activity_change"
    ADD_INGOTS = "add_ingots"
    REMOVE_INGOTS = "remove_ingots"
    RANK_CHANGE = "rank_change"


class Changelog(Base):
    __tablename__ = "changelog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("members.id"), nullable=False)
    admin_id: Mapped[str] = mapped_column(ForeignKey("members.id"), nullable=True)
    change_type: Mapped[ChangeType] = mapped_column(String, nullable=False)
    previous_value: Mapped[str] = mapped_column(String, nullable=True)
    new_value: Mapped[str] = mapped_column(String, nullable=True)
    comment: Mapped[str] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
