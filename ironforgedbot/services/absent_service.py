import logging

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.decorators import retry_on_exception
from ironforgedbot.models.absent_member import AbsentMember
from ironforgedbot.services.member_service import MemberService
from ironforgedbot.storage.sheets import Sheets

logger = logging.getLogger(__name__)


class AbsentMemberService:
    def __init__(self, db: AsyncSession):
        self.sheet = Sheets()
        self.member_service = MemberService(db)
        self.sheet_name = "AbsenceNotice"

    @retry_on_exception(3)
    async def get_absentees(self) -> list[AbsentMember]:
        data = await self.sheet.get_range(self.sheet_name, "A2:F")

        if not data:
            return []

        members = []
        for entry in data:
            members.append(
                AbsentMember(
                    entry[0],
                    int(entry[1] or 0),
                    entry[2],
                    entry[3] if len(entry) > 3 else "",
                    entry[4] if len(entry) > 4 else "",
                    entry[5] if len(entry) > 5 else "",
                )
            )

        return members

    @retry_on_exception(3)
    async def update_absentees(self, absentees: list[AbsentMember]) -> None:
        values = []

        for member in absentees:
            values.append(
                [
                    member.id,
                    str(member.discord_id),
                    member.nickname,
                    member.date,
                    member.information,
                    member.comment,
                ]
            )

        await self.sheet.update_range(self.sheet_name, f"A2:F{len(values) + 1}", values)

    # TODO: check how it acts when a nickname gets removed
    async def process_absent_members(self) -> list[AbsentMember]:
        absentees = await self.get_absentees()

        for storage_member in absentees:
            if storage_member.id:
                member = await self.member_service.get_member_by_id(storage_member.id)
            else:
                member = await self.member_service.get_member_by_nickname(
                    storage_member.nickname
                )

            if not member:
                storage_member.information = "Member not found in database."
                continue

            if not member.active:
                storage_member.information = "Member has left the clan."
                continue

            updated = False
            if storage_member.nickname != member.nickname:
                storage_member.nickname = member.nickname
                storage_member.information = "Updated nickname."
                updated = True

            if not storage_member.id or len(storage_member.id) < 1:
                storage_member.id = member.id
                updated = True

            if not storage_member.discord_id:
                storage_member.discord_id = member.discord_id
                updated = True

            if not updated:
                storage_member.information = ""

        await self.update_absentees(absentees)
        return absentees
