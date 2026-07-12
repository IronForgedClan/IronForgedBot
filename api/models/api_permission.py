from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ironforgedbot.database.database import Base
from ironforgedbot.models.decorators import UTCDateTime


class ApiPermission(Base):
    __tablename__ = "api_permissions"

    name: Mapped[str] = mapped_column(String(length=64), primary_key=True)
    description: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(tz=timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"ApiPermission(name={self.name!r})"
