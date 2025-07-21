#!/usr/bin/env python3
import asyncio
import os
import sys


# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ironforgedbot.database.database import db

from datetime import datetime, timezone
import uuid
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy.orm.session import Session

from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.ranks import RANK
from ironforgedbot.models.changelog import ChangeType, Changelog
from ironforgedbot.models.member import Member


def get_sheet_data(sheet_name, worksheet_name) -> list[any]:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name)
    worksheet = sheet.worksheet(worksheet_name)

    all_rows = worksheet.get_all_values()

    headers = ["RSN", "Ingots", "Id", "Joined Date"]

    data = []

    for row in all_rows[1:]:
        trimmed = row[:4]
        while len(trimmed) < 4:
            trimmed.append("")

        data.append(dict(zip(headers, trimmed)))

    return data


async def import_membes(sheet_data) -> None:
    async for session in db.get_session():
        for row in sheet_data:
            new_member_id: str = str(uuid.uuid4())
            now: datetime = datetime.now(tz=timezone.utc)
            nick: str = normalize_discord_string(input=row["RSN"])

            joined = datetime.fromisoformat(row["Joined Date"])

            member: Member = Member(
                id=new_member_id,
                discord_id=row["Id"],
                active=True,
                nickname=nick,
                ingots=int(row["Ingots"]),
                rank=RANK.IRON,
                joined_date=joined,
                last_changed_date=now,
            )

            changelog_entry: Changelog = Changelog(
                member_id=new_member_id,
                change_type=ChangeType.ADD_MEMBER,
                previous_value=None,
                new_value=None,
                comment="Added member (import)",
                timestamp=now,
            )

            try:
                session.add(instance=member)
                session.add(instance=changelog_entry)
                await session.commit()
                print(f"Imported {member.nickname}")
            except Exception as e:
                await session.rollback()
                print(f"Error: {e}")

        await session.close()


async def main():
    sheet_members = get_sheet_data("IronForged_bot_test", "ClanIngots")

    await import_membes(sheet_members)


if __name__ == "__main__":
    asyncio.run(main())
