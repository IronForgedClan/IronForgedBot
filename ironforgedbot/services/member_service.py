from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ironforgedbot.common.ranks import RANK
from models.member import Member


class MemberService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_member(self, discord_id: int, nickname: str):
        member = Member(
            discord_id=discord_id,
            active=True,
            nickname=nickname,
            ingots=0,
            rank=RANK.ADAMANT,
            joined_date=datetime.now(),
        )

        self.session.add(member)
        await self.session.commit()
        return member

    async def get_member_by_id(self, id: str) -> Member | None:
        result = await self.session.execute(select(Member).where(Member.id == id))
        return result.scalars().first()

    async def get_member_by_discord_id(self, id: str):
        result = await self.session.execute(
            select(Member).where(Member.discord_id == id)
        )
        return result.scalars().first()

    async def get_member_by_nickname(self, nickname: str):
        result = await self.session.execute(
            select(Member).where(Member.nickname == nickname)
        )
        return result.scalars().first()
