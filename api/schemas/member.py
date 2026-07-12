from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.models import Member


class MemberSummary(BaseModel):
    id: str
    discord_id: int
    nickname: str
    role: str
    rank: str
    joined_date: datetime | None = None
    is_booster: bool
    is_prospect: bool
    is_blacklisted: bool
    is_banned: bool

    @classmethod
    def from_member(cls, member: Member) -> "MemberSummary":
        return cls(
            id=member.id,
            discord_id=member.discord_id,
            nickname=member.nickname,
            role=(
                member.role.value if isinstance(member.role, Enum) else str(member.role)
            ),
            rank=(
                member.rank.value if isinstance(member.rank, Enum) else str(member.rank)
            ),
            joined_date=member.joined_date,
            is_booster=member.is_booster,
            is_prospect=member.is_prospect,
            is_blacklisted=member.is_blacklisted,
            is_banned=member.is_banned,
        )


class MemberFilter(str, Enum):
    ACTIVE = "active"
    BOOSTER = "booster"
    PROSPECT = "prospect"
    BLACKLISTED = "blacklisted"
    BANNED = "banned"


class MemberQueryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    role: ROLE | None = None
    rank: RANK | None = None
    filter: MemberFilter | None = None
