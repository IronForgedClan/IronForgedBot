#!/usr/bin/env python3
import asyncio
import os
import sys

# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uuid
import gspread

from datetime import datetime, timezone
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy.orm.session import Session

from ironforgedbot.exceptions.score_exceptions import HiscoresError, HiscoresNotFound
from ironforgedbot.http import HTTP, HttpException
from ironforgedbot.services.score_service import ScoreService
from ironforgedbot.database.database import db
from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.common.ranks import RANK, get_rank_from_points
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


async def _get_rank(name: str) -> str:
    try:
        await asyncio.sleep(2)
        data = await ScoreService(HTTP).get_player_points_total(name)
        rank = get_rank_from_points(data)
        print(f"  {name} has {data} points and is {rank} rank")
        return rank
    except (HiscoresError, HttpException):
        print(f"  {name} hiscores error, saving as Iron")
    except HiscoresNotFound:
        print(f"  {name} not on hiscores, saving as Iron")

    return RANK.IRON


async def import_membes(sheet_data) -> None:
    async with db.get_session() as session:
        for row in sheet_data:
            new_member_id: str = str(uuid.uuid4())
            now: datetime = datetime.now(tz=timezone.utc)
            nick: str = normalize_discord_string(input=row["RSN"])

            print(f"\nprocessing {nick}...")

            try:
                joined = datetime.fromisoformat(row["Joined Date"])
            except Exception as e:
                print(f"! {nick} invalid join date: '{row['Joined Date']}'")
                continue

            member = Member(
                id=new_member_id,
                discord_id=row["Id"],
                active=True,
                nickname=nick,
                ingots=int(row["Ingots"]),
                rank=await _get_rank(nick),
                joined_date=joined,
                last_changed_date=now,
            )

            changelog_entry = Changelog(
                member_id=new_member_id,
                change_type=ChangeType.ADD_MEMBER,
                previous_value=None,
                new_value=None,
                comment="Added member (import)",
                timestamp=now,
            )

            try:
                session.add(instance=member)
                await session.flush()
                session.add(instance=changelog_entry)
                await session.commit()
                print(f"  rank: {member.rank}")
                print(f"  ingots: {member.ingots}")
                print(f"  join date: {member.joined_date}")
                print(f"+ imported {member.nickname}")
            except Exception as e:
                error_message = str(e)
                await session.rollback()

                if "discord_id" in error_message:
                    print(f"- {nick} discord id already exists")
                elif "nickname" in error_message:
                    print(f"- {nick} nickname already exists")
                else:
                    print(f"- {nick} unhandled error:")
                    print(e)


async def main():
    sheet = sys.argv[1]
    if not sheet:
        print("No sheet specified")
        print("Expected eg: IronForged_bot_test")
        sys.exit(1)
    print(f"fetching {sheet} Sheets data...")
    sheet_members = get_sheet_data(sheet, "ClanIngots")
    print(f"found {len(sheet_members)} rows of data\n")
    await import_membes(sheet_members)


if __name__ == "__main__":
    asyncio.run(main())
