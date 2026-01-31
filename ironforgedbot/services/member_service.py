from dataclasses import dataclass
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.logging_utils import log_database_operation
from ironforgedbot.common.ranks import RANK
from ironforgedbot.common.roles import ROLE
from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.models.member import Member


class UniqueNicknameViolation(Exception):
    def __init__(self, message: str = "This nickname already exists") -> None:
        self.message: str = message
        super().__init__(self.message)


class UniqueDiscordIdVolation(Exception):
    def __init__(self, message: str = "This discord id already exists") -> None:
        self.message: str = message
        super().__init__(self.message)


class MemberNotFoundException(Exception):
    def __init__(self, message: str = "The member can not be found") -> None:
        self.message: str = message
        super().__init__(self.message)


@dataclass
class MemberServiceReactivateResponse:
    status: bool
    previous_nick: str
    ingots_reset: bool
    previous_ingot_qty: int
    previous_join_date: datetime
    approximate_leave_date: datetime
    previous_rank: RANK
    new_member: Member


logger: logging.Logger = logging.getLogger(name=__name__)

MEMBER_FLAGS = frozenset({"is_booster", "is_prospect", "is_blacklisted", "is_banned"})


class MemberService:
    def __init__(self, db: AsyncSession) -> None:
        self.db: AsyncSession = db

    async def close(self) -> None:
        await self.db.close()

    @log_database_operation(logger)
    async def create_member(
        self,
        discord_id: int,
        nickname: str,
        rank: RANK | None = RANK.IRON,
        admin_id: str | None = None,
    ) -> Member:
        new_member_id: str = str(uuid.uuid4())
        now: datetime = datetime.now(tz=timezone.utc)
        nick: str = normalize_discord_string(input=nickname)

        member: Member = Member(
            id=new_member_id,
            discord_id=discord_id,
            active=True,
            nickname=nick,
            ingots=0,
            rank=rank,
            joined_date=now,
            last_changed_date=now,
        )

        changelog_entry: Changelog = Changelog(
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
            await self.db.flush()
            self.db.add(changelog_entry)
            await self.db.commit()
        except IntegrityError as e:
            error_message = str(e)
            await self.db.rollback()

            if "discord_id" in error_message:
                raise UniqueDiscordIdVolation()
            elif "nickname" in error_message:
                raise UniqueNicknameViolation()
            else:
                raise e
        except Exception as e:
            logger.critical(e)
            await self.db.rollback()
            raise

        return member

    async def get_all_active_members(self) -> list[Member]:
        result = await self.db.execute(select(Member).where(Member.active.is_(True)))
        return list(result.scalars().all())

    async def get_active_members_by_role(self, role: ROLE) -> list[Member]:
        """Get all active members with a specific role."""
        result = await self.db.execute(
            select(Member).where(Member.active.is_(True), Member.role == role)
        )
        return list(result.scalars().all())

    async def get_active_boosters(self) -> list[Member]:
        """Get all active members who are server boosters."""
        result = await self.db.execute(
            select(Member).where(Member.active.is_(True), Member.is_booster.is_(True))
        )
        return list(result.scalars().all())

    async def get_active_prospects(self) -> list[Member]:
        """Get all active members who are prospects."""
        result = await self.db.execute(
            select(Member).where(Member.active.is_(True), Member.is_prospect.is_(True))
        )
        return list(result.scalars().all())

    async def get_blacklisted_members(self) -> list[Member]:
        """Get all active members who are blacklisted."""
        result = await self.db.execute(
            select(Member).where(
                Member.active.is_(True), Member.is_blacklisted.is_(True)
            )
        )
        return list(result.scalars().all())

    async def get_banned_members(self) -> list[Member]:
        """Get all members who are banned."""
        result = await self.db.execute(select(Member).where(Member.is_banned.is_(True)))
        return list(result.scalars().all())

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

    async def get_member_rank(self, nickname: str) -> RANK | None:
        result = await self.db.execute(
            select(Member.rank).where(Member.nickname == nickname)
        )
        return result.scalar_one_or_none()

    @log_database_operation(logger)
    async def reactivate_member(
        self, id: str, new_nickname: str, rank: RANK | None = RANK.IRON
    ) -> MemberServiceReactivateResponse:
        now = datetime.now(timezone.utc)
        member = await self.get_member_by_id(id)
        if not member:
            raise MemberNotFoundException(f"Member with id {id} does not exist")

        response = MemberServiceReactivateResponse(
            status=False,
            previous_nick=member.nickname,
            ingots_reset=False,
            previous_ingot_qty=member.ingots,
            previous_join_date=member.joined_date,
            approximate_leave_date=member.last_changed_date,
            previous_rank=member.rank,
            new_member=member,
        )

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
                comment="Join date updated during reactivation",
                timestamp=now,
            )
        )
        member.joined_date = now

        if now > member.last_changed_date + timedelta(days=1):
            self.db.add(
                Changelog(
                    member_id=member.id,
                    admin_id=None,
                    change_type=ChangeType.RESET_INGOTS,
                    previous_value=member.ingots,
                    new_value=0,
                    comment="Ingots reset during reactivation",
                    timestamp=now,
                )
            )
            response.ingots_reset = True
            member.ingots = 0

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

        if member.rank != rank:
            self.db.add(
                Changelog(
                    member_id=member.id,
                    admin_id=None,
                    change_type=ChangeType.RANK_CHANGE,
                    previous_value=member.rank,
                    new_value=rank,
                    comment="Rank changed during reactivation",
                    timestamp=now,
                )
            )
            member.rank = RANK(rank)

        member.last_changed_date = now

        try:
            await self.db.commit()
            await self.db.refresh(member)
        except IntegrityError as e:
            if "nickname" in str(e):
                await self.db.rollback()
                raise UniqueNicknameViolation()
            else:
                raise e
        except Exception as e:
            logger.critical(e)
            await self.db.rollback()
            raise

        response.status = True
        response.new_member = member

        return response

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

        try:
            await self.db.commit()
            await self.db.refresh(member)
        except Exception as e:
            logger.critical(e)
            await self.db.rollback()
            raise e

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

            if "nickname" in error_message:
                await self.db.rollback()
                raise UniqueNicknameViolation()
            else:
                raise e
        except Exception as e:
            logger.critical(e)
            await self.db.rollback()
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

        try:
            self.db.add(changelog_entry)
            await self.db.commit()
            await self.db.refresh(member)
        except Exception as e:
            logger.critical(e)
            await self.db.rollback()
            raise e

        return member

    async def change_role(
        self, id: str, new_role: ROLE, admin_id: str | None = None
    ) -> Member:
        member = await self.get_member_by_id(id)

        if not member:
            raise MemberNotFoundException(f"Member with id {id} does not exist")

        now = datetime.now(timezone.utc)

        changelog_entry = Changelog(
            member_id=member.id,
            admin_id=admin_id,
            change_type=ChangeType.ROLE_CHANGE,
            previous_value=member.role,
            new_value=new_role,
            comment="Updated role",
            timestamp=now,
        )

        member.role = new_role
        member.last_changed_date = now

        try:
            self.db.add(changelog_entry)
            await self.db.commit()
            await self.db.refresh(member)
        except Exception as e:
            logger.critical(e)
            await self.db.rollback()
            raise e

        return member

    async def update_member_flags(self, id: str, **flags: bool) -> Member:
        """Update boolean flags on a member.

        Args:
            id: Member ID
            **flags: Flag name/value pairs (is_booster, is_prospect, is_blacklisted, is_banned)

        Only creates changelog entries for flags that actually change.
        Raises ValueError for unknown flag names.
        """
        unknown_flags = set(flags.keys()) - MEMBER_FLAGS
        if unknown_flags:
            raise ValueError(f"Unknown flag(s): {unknown_flags}")

        now = datetime.now(timezone.utc)
        member = await self.get_member_by_id(id)

        if not member:
            raise MemberNotFoundException(f"Member with id {id} does not exist")

        changelog_entries: list[Changelog] = []

        for flag_name, new_value in flags.items():
            current_value = getattr(member, flag_name)
            if new_value != current_value:
                changelog_entries.append(
                    Changelog(
                        member_id=member.id,
                        admin_id=None,
                        change_type=ChangeType.FLAG_CHANGE,
                        previous_value=current_value,
                        new_value=new_value,
                        comment=f"Updated {flag_name.replace('is_', '')} flag",
                        timestamp=now,
                    )
                )
                setattr(member, flag_name, new_value)

        if not changelog_entries:
            logger.warning("No flag changes detected")
            return member

        member.last_changed_date = now

        try:
            for entry in changelog_entries:
                self.db.add(entry)
            await self.db.commit()
            await self.db.refresh(member)
        except Exception as e:
            logger.critical(e)
            await self.db.rollback()
            raise e

        return member
