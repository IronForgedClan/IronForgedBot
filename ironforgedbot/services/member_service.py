import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.ranks import RANK
from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.models.member import Member


class UniqueNicknameViolation(Exception):
    def __init__(self, message="This nickname already exists"):
        self.message = message
        super().__init__(self.message)


class UniqueDiscordIdVolation(Exception):
    def __init__(self, message="This discord id already exists"):
        self.message = message
        super().__init__(self.message)


class MemberNotFoundException(Exception):
    def __init__(self, message="The member can not be found"):
        self.message = message
        super().__init__(self.message)


class MemberService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def close(self):
        await self.db.close()

    async def create_member(
        self, discord_id: int, nickname: str, admin_id: Optional[str] = None
    ) -> Member:
        new_member_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

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

        try:
            self.db.add(member)
            self.db.add(changelog_entry)
            await self.db.commit()
        except IntegrityError as e:
            error_message = str(e)

            if "members.discord_id" in error_message:
                await self.db.rollback()
                raise UniqueDiscordIdVolation()
            elif "members.nickname" in error_message:
                await self.db.rollback()
                raise UniqueNicknameViolation()
            else:
                raise e

        return member

    async def create_or_activate(
        self, discord_id: int, nickname: str, admin_id: Optional[str] = None
    ) -> Member:
        try:
            member = await self.create_member(discord_id, nickname, admin_id)
            return member
        except UniqueDiscordIdVolation:
            existing_member = await self.get_member_by_discord_id(discord_id)
            if not existing_member:
                raise Exception("Member not found")

        return await self.disable_member(existing_member.id)

    async def get_all_active_members(self):
        result = await self.db.execute(select(Member).where(Member.active == True))
        return result.scalars().all()

    async def get_member_by_id(self, id: str) -> Member | None:
        result = await self.db.execute(select(Member).where(Member.id == id))
        return result.scalars().first()

    async def get_member_by_discord_id(self, discord_id: int) -> Member | None:
        result = await self.db.execute(
            select(Member).where(Member.discord_id == discord_id)
        )
        return result.scalars().first()

    async def get_member_by_nickname(self, nickname: str) -> Member | None:
        result = await self.db.execute(
            select(Member).where(Member.nickname == nickname)
        )
        return result.scalars().first()

    async def reactivate_member(self, id: str, new_nickname: str) -> Member:
        member = await self.get_member_by_id(id)
        if not member:
            raise MemberNotFoundException(f"Member with id {id} does not exist")

        now = datetime.now(timezone.utc)

        self.db.add(
            Changelog(
                member_id=member.id,
                admin_id=None,
                change_type=ChangeType.ACTIVITY_CHANGE,
                previous_value=member.active,
                new_value=True,
                comment="Returning member",
                timestamp=now,
            )
        )
        member.active = True

        self.db.add(
            Changelog(
                member_id=member.id,
                admin_id=None,
                change_type=ChangeType.JOINED_DATE_CHANGE,
                previous_value=member.joined_date,
                new_value=now,
                comment="Returning member updated join timestamp",
                timestamp=now,
            )
        )
        member.joined_date = now

        if member.nickname != new_nickname:
            self.db.add(
                Changelog(
                    member_id=member.id,
                    admin_id=None,
                    change_type=ChangeType.NAME_CHANGE,
                    previous_value=member.nickname,
                    new_value=new_nickname,
                    comment="Nickname changed during reactivation",
                    timestamp=now,
                )
            )
            member.nickname = new_nickname

        member.last_changed_date = now

        try:
            await self.db.commit()
            await self.db.refresh(member)
        except IntegrityError as e:
            if "members.nickname" in str(e):
                await self.db.rollback()
                raise UniqueNicknameViolation()
            else:
                raise e

        return member

    async def disable_member(self, id: str) -> Member:
        member = await self.get_member_by_id(id)
        if not member:
            raise MemberNotFoundException(f"Member with id {id} does not exist")

        now = datetime.now(timezone.utc)

        self.db.add(
            Changelog(
                member_id=member.id,
                admin_id=None,
                change_type=ChangeType.ACTIVITY_CHANGE,
                previous_value=member.active,
                new_value=False,
                comment="Disabled member",
                timestamp=now,
            )
        )
        member.active = False
        member.last_changed_date = now

        await self.db.commit()
        await self.db.refresh(member)

        return member

    async def change_nickname(self, id: str, new_nickname: str) -> Member:
        member = await self.get_member_by_id(id)

        if not member:
            raise MemberNotFoundException(f"Member with id {id} does not exist")

        now = datetime.now(timezone.utc)

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

        try:
            self.db.add(changelog_entry)
            await self.db.commit()
            await self.db.refresh(member)
        except IntegrityError as e:
            error_message = str(e)

            if "members.nickname" in error_message:
                await self.db.rollback()
                raise UniqueNicknameViolation()
            else:
                raise e

        return member

    async def change_rank(self, id: str, new_rank: RANK) -> Member:
        member = await self.get_member_by_id(id)

        if not member:
            raise MemberNotFoundException(f"Member with id {id} does not exist")

        now = datetime.now(timezone.utc)

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
