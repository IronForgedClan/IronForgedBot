from datetime import datetime, timezone
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from ironforgedbot.database.database import Base
from ironforgedbot.models.decorators import UTCDateTime


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[str] = mapped_column(
        String(length=36), ForeignKey(column="members.id"), nullable=False
    )
    nickname: Mapped[str] = mapped_column(
        String(length=12), unique=True, nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(tz=timezone.utc)
    )
