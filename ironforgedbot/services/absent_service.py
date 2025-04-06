import logging

from ironforgedbot.decorators import retry_on_exception
from ironforgedbot.models.absent_member import AbsentMember
from ironforgedbot.storage.sheets import Sheets


logger = logging.getLogger(__name__)


class AbsentMemberService:
    def __init__(self):
        self.sheet = Sheets()
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
