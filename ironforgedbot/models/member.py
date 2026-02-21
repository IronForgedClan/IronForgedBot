from datetime import datetime, timezone
import uuid
from sqlalchemy import BigInteger, Boolean, String, Enum
from sqlalchemy.orm import Mapped, mapped_column
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.database.database import Base
from ironforgedbot.models.decorators import UTCDateTime


class Member(Base):
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(
        String(length=36),
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    discord_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(
        String(length=12), unique=True, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[ROLE] = mapped_column(
        Enum(ROLE, native_enum=False), nullable=False, default=ROLE.GUEST
    )
    rank: Mapped[RANK] = mapped_column(Enum(RANK, native_enum=False), nullable=False)
    ingots: Mapped[int] = mapped_column(BigInteger, default=0)
    joined_date: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(tz=timezone.utc)
    )
    last_changed_date: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(tz=timezone.utc)
    )
    is_booster: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_prospect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
