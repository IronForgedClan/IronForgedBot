from datetime import datetime, timezone
import secrets

from sqlalchemy import JSON, BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from ironforgedbot.database.database import Base
from ironforgedbot.models.decorators import UTCDateTime


def _generate_token() -> str:
    return f"if_live_{secrets.token_urlsafe(32)}"


class ApiConsumer(Base):
    __tablename__ = "api_consumers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(length=64), unique=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(
        String(length=128), unique=True, nullable=False
    )
    perms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(tz=timezone.utc), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True, default=None
    )
    description: Mapped[str | None] = mapped_column(String(length=255), nullable=True)

    def __repr__(self) -> str:
        return f"ApiConsumer(id={self.id}, name={self.name!r}, enabled={self.enabled})"
