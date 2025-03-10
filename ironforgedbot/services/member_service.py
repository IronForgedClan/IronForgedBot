from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.ranks import RANK
from ironforgedbot.models.changelog import ChangeType, Changelog
from ironforgedbot.models.member import Member


class MemberService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_member(
        self, discord_id: int, nickname: str, admin_id: Optional[str] = None
    ) -> Member:
        new_member_id = str(uuid.uuid4())
        now = datetime.now()

        member = Member(
            id=new_member_id,
            discord_id=discord_id,
            active=True,
            nickname=nickname,
            ingots=0,
            rank=RANK.ADAMANT,
            joined_date=now,
            last_changed_date=now,
        )

        changelog_entry = Changelog(
            member_id=new_member_id,
            admin_id=admin_id,
            change_type=ChangeType.ADD_MEMBER,
            previous_value=None,
            new_value=None,
            comment="Added member",
            timestamp=now,
        )

        self.db.add(member)
        self.db.add(changelog_entry)
        await self.db.commit()

        return member

    async def get_all_active_members(self):
        result = await self.db.execute(select(Member).where(Member.active == True))
        return result.scalars().all()

    async def get_member_by_id(self, id: str) -> Member | None:
        result = await self.db.execute(select(Member).where(Member.id == id))
        return result.scalars().first()

    async def get_member_by_nickname(self, nickname: str):
        result = await self.db.execute(
            select(Member).where(Member.nickname == nickname)
        )
        return result.scalars().first()

    async def change_activity(self, id: str, active: bool) -> Member:
        member = await self.get_member_by_id(id)

        if not member:
            # todo: nicer exceptions
            raise Exception("Member with id does not exist")

        now = datetime.now()

        changelog_entry = Changelog(
            member_id=member.id,
            admin_id=None,
            change_type=ChangeType.ACTIVITY_CHANGE,
            previous_value=member.active,
            new_value=active,
            comment="Enabled member" if active else "Disabled member",
            timestamp=now,
        )

        member.active = active
        member.last_changed_date = now

        self.db.add(changelog_entry)
        await self.db.commit()
        await self.db.refresh(member)

        return member

    async def change_nickname(self, id: str, new_nickname: str) -> Member:
        member = await self.get_member_by_id(id)

        if not member:
            # todo: nicer exceptions
            raise Exception("Member with id does not exist")

        now = datetime.now()

        changelog_entry = Changelog(
            member_id=member.id,
            admin_id=None,
            change_type=ChangeType.NAME_CHANGE,
            previous_value=member.nickname,
            new_value=new_nickname,
            comment="Updated nickname",
            timestamp=now,
        )

        member.nickname = new_nickname
        member.last_changed_date = now

        self.db.add(changelog_entry)
        await self.db.commit()
        await self.db.refresh(member)

        return member

    async def change_rank(self, id: str, new_rank: RANK) -> Member:
        member = await self.get_member_by_id(id)

        if not member:
            # todo: nicer exceptions
            raise Exception("Member with id does not exist")

        now = datetime.now()

        changelog_entry = Changelog(
            member_id=member.id,
            admin_id=None,
            change_type=ChangeType.RANK_CHANGE,
            previous_value=member.rank,
            new_value=new_rank,
            comment="Updated rank",
            timestamp=now,
        )

        member.rank = new_rank
        member.last_changed_date = now

        self.db.add(changelog_entry)
        await self.db.commit()
        await self.db.refresh(member)

        return member
