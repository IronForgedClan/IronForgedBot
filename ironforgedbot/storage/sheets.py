import asyncio
import logging
import sys
from datetime import datetime
from typing import Dict, List, Union

from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build
import pytz

from ironforgedbot.event_emitter import event_emitter
from ironforgedbot.common.helpers import normalize_discord_string
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators import retry_on_exception
from ironforgedbot.storage.types import IngotsStorage, Member, StorageError

logging.getLogger("googleapiclient").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_RANGE = "ClanIngots!A2:B"
SHEET_RANGE_WITH_DISCORD_IDS = "ClanIngots!A2:D"
RAFFLE_RANGE = "ClanRaffle!A2"
RAFFLE_TICKETS_RANGE = "ClanRaffleTickets!A2:B"
CHANGELOG_RANGE = "ChangeLog!A2:F"
ABSENCE_RANGE = "AbsenceNotice!A2:C"


class SheetsStorage(metaclass=IngotsStorage):
    """A storage implementation backed by Sheets.

    Expected schema is a sheet with two tabs:
        ClanIngots: RSN, ingots, Discord ID
        ChangeLog: Timestamp (EST), previous value, new value,
            update reason, manual note.
    """

    def __init__(self, sheets_client: Resource, sheet_id: str):
        """Init.

        Arguments:
            sheets_client: Built Resource object to interact with
                sheets API.
            sheet_id: ID of sheets to connect to.
        """
        self._sheets_client = sheets_client
        self._sheet_id = sheet_id
        self._lock = asyncio.Lock()

        event_emitter.on("shutdown", self.shutdown, priority=20)

    @classmethod
    def from_account_file(cls, account_filepath: str, sheet_id: str) -> "SheetsStorage":
        """Build sheets Resource from service account file."""
        creds = service_account.Credentials.from_service_account_file(
            account_filepath, scopes=SHEETS_SCOPES
        )
        service = build("sheets", "v4", credentials=creds)

        return cls(service, sheet_id)

    def _get_timestamp(self) -> str:
        utc_now = datetime.now(pytz.utc)
        est_tz = pytz.timezone("America/New_York")
        est_now = utc_now.astimezone(est_tz)

        return est_now.strftime("%Y-%m-%d %H:%M:%S %Z%z")

    @retry_on_exception(retries=5)
    async def _get_sheet_data(self, spreadsheet_id, range_name):
        """Performs a thread-safe fetch of sheet data.

        Arguments:
            spreadsheet_id: int
            range_name: str
        """
        async with self._lock:
            query = (
                self._sheets_client.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_name)
            )

            result = await asyncio.to_thread(query.execute)
            return result.get("values", None)

    @retry_on_exception(retries=5)
    async def _update_sheet_data(self, spreadsheet_id, range_name, body):
        """Performs a thread-safe update to sheet data.

        Arguments:
            spreadsheet_id: int
            range_name: str
            body: any
        """
        async with self._lock:
            query = (
                self._sheets_client.spreadsheets()
                .values()
                .update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body=body,
                )
            )

            return await asyncio.to_thread(query.execute)

    @retry_on_exception(retries=5)
    async def _append_sheet_data(self, spreadsheet_id, range_name, body):
        """Performs a thread-safe append to sheet data.

        Arguments:
            spreadsheet_id: int
            range_name: str
            body: any
        """
        async with self._lock:
            query = (
                self._sheets_client.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body=body,
                )
            )

            return await asyncio.to_thread(query.execute)

    async def _log_change(self, changes: list[list[Union[str, int]]]):
        """Records data change to ChangeLog sheet.

        Arguments:
            changes: Values to prepend to current changelog. Expected
                format: [user, timestamp, old value, new value, mutator, note]
        """
        body = {"values": changes}
        await self._append_sheet_data(self._sheet_id, CHANGELOG_RANGE, body)

    async def read_changelog(self):
        """Returns entire changelog table."""
        return await self._get_sheet_data(self._sheet_id, CHANGELOG_RANGE)

    async def read_member(self, player: str) -> Member | None:
        """Read member by runescape name."""
        members = await self.read_members()

        for member in members:
            if member.runescape_name.lower() == normalize_discord_string(
                player.lower()
            ):
                return member

        return None

    async def read_members(self) -> List[Member]:
        """Get all members from storage."""
        result = await self._get_sheet_data(
            self._sheet_id, SHEET_RANGE_WITH_DISCORD_IDS
        )

        members = []
        for value in result:
            # ingot values stored as strings to allow for large numbers
            try:
                member_ingots = int(value[1])
            except ValueError as e:
                logger.error(e)
                raise StorageError("Invalid ingot value for user.")

            # legacy members won't have a valid joined date set
            try:
                member_joined_date = datetime.fromisoformat(value[3].strip())
            except ValueError as e:
                logger.error(e)
                member_joined_date = "unknown"

            member = Member(
                id=int(value[2]),
                runescape_name=value[0],
                ingots=member_ingots,
                joined_date=member_joined_date,
            )

            members.append(member)

        return members

    async def add_members(
        self, members: List[Member], attribution: str, note: str = ""
    ):
        """Add new members to sheet."""
        existing = await self.read_members()
        existing.extend(members)

        existing.sort(key=lambda x: x.runescape_name)

        # We're only adding members, so the length can only increase.
        write_range = f"ClanIngots!A2:D{2 + len(existing)}"
        body = {
            "values": [
                [member.runescape_name, member.ingots, str(member.id)]
                for member in existing
            ]
        }

        await self._update_sheet_data(self._sheet_id, write_range, body)

        changes = [
            [member.runescape_name, self._get_timestamp(), 0, 0, attribution, note]
            for member in members
        ]

        await self._log_change(changes)

    async def update_members(
        self, members: List[Member], attribution: str, note: str = ""
    ):
        """Update existing members."""
        changes = []
        existing = await self.read_members()

        for member in members:
            for i, existing_member in enumerate(existing):
                if member.id == existing_member.id:
                    changes.append(
                        [
                            existing_member.runescape_name,
                            self._get_timestamp(),
                            str(existing_member),
                            str(member),
                            attribution,
                            note,
                        ]
                    )
                    existing[i] = member
                    break

        # Sort by RSN for output stability
        existing.sort(key=lambda x: x.runescape_name)

        write_range = f"ClanIngots!A2:D{2 + len(existing)}"

        # save ingots as a string to allow for large numbers
        # while maintaining accuracy
        body = {
            "values": [
                [
                    member.runescape_name,
                    str(member.ingots),
                    str(member.id),
                    member.joined_date,
                ]
                for member in existing
            ]
        }

        await self._update_sheet_data(self._sheet_id, write_range, body)
        await self._log_change(changes)

    async def remove_members(
        self, members: List[Member], attribution: str, note: str = ""
    ):
        """Remove members from storage."""
        changes = []
        filtered_values = []
        existing = await self.read_members()
        remove_ids = [member.id for member in members]

        for member in existing:
            if member.id in remove_ids:
                changes.append(
                    [
                        member.runescape_name,
                        self._get_timestamp(),
                        str(member),
                        0,
                        attribution,
                        note,
                    ]
                )
                continue
            filtered_values.append(member)

        # Sort by RSN for output stability.
        filtered_values.sort(key=lambda x: x.runescape_name)
        rows = [
            [member.runescape_name, member.ingots, str(member.id)]
            for member in filtered_values
        ]

        # Pad empty values to actually remove members from the sheet.
        for _ in range(len(existing) - len(filtered_values)):
            rows.append(["", "", ""])

        write_range = f"ClanIngots!A2:D{2 + len(existing)}"
        body = {"values": rows}

        await self._update_sheet_data(self._sheet_id, write_range, body)
        await self._log_change(changes)

    async def read_raffle(self) -> bool:
        """Reads if a raffle is currently ongoing."""
        result = await self._get_sheet_data(self._sheet_id, RAFFLE_RANGE)

        if len(result) < 1:
            return False
        if len(result[0]) < 1:
            return False
        if result[0][0] != "True":
            return False
        return True

    async def start_raffle(self, attribution: str) -> None:
        """Starts a raffle, enabling purchase of raffle tickets."""
        if await self.read_raffle():
            raise StorageError("There is already a raffle ongoing")

        body = {"values": [["True"]]}

        await self._update_sheet_data(self._sheet_id, RAFFLE_RANGE, body)

        changes = [
            [
                "",
                self._get_timestamp(),
                "False",
                "True",
                attribution,
                "Started Raffle",
            ]
        ]

        await self._log_change(changes)

    async def end_raffle(self, attribution: str) -> None:
        """Marks a raffle as over, blocking purchase of tickets."""
        if not await self.read_raffle():
            raise StorageError("There is no currently ongoing raffle")

        body = {"values": [["False"]]}

        await self._update_sheet_data(self._sheet_id, RAFFLE_RANGE, body)

        changes = [
            ["", self._get_timestamp(), "True", "False", attribution, "Ended Raffle"]
        ]

        await self._log_change(changes)

    async def read_raffle_tickets(self) -> Dict[int, int]:
        """Reads number of tickets a user has for the current raffle."""
        result = await self._get_sheet_data(self._sheet_id, RAFFLE_TICKETS_RANGE)

        # Unlike the ingots table, this is expected to get emptied.
        # So we have to account for an empty response.
        tickets = {}
        if result:
            for value in result:
                if len(value) >= 2:
                    if value[0] == "":
                        continue
                    if value[1] == "":
                        value[1] = 0
                    tickets[int(value[0])] = int(value[1])

        return tickets

    async def add_raffle_tickets(self, member_id: int, tickets: int) -> None:
        """Add tickets to a given member."""
        changes = []

        # If user is in storage, add tickets. Otherwise, add them to storage.
        new_count = tickets
        existing_count = 0
        current_tickets = await self.read_raffle_tickets()

        for id, current_count in current_tickets.items():
            if id == member_id:
                existing_count = current_count
                new_count = current_count + tickets

        current_tickets[member_id] = int(new_count)
        changes.append(
            [
                member_id,
                self._get_timestamp(),
                existing_count,
                int(new_count),
                member_id,
                f"Assign {tickets} raffle tickets",
            ]
        )

        # Convert to list for write & sort for stability.
        values = []
        for id, current_count in current_tickets.items():
            values.append([str(id), current_count])

        values.sort(key=lambda x: x[0])

        write_range = f"ClanRaffleTickets!A2:B{2 + len(values)}"
        body = {"values": values}

        await self._update_sheet_data(self._sheet_id, write_range, body)
        await self._log_change(changes)

    async def delete_raffle_tickets(self, attribution: str) -> None:
        """Deletes all raffle tickets."""
        changes = []
        changes.append(
            [
                "",
                self._get_timestamp(),
                "",
                "",
                attribution,
                "Cleared all raffle tickets",
            ]
        )

        values = []
        current_tickets = await self.read_raffle_tickets()
        for _, _ in current_tickets.items():
            values.append(["", ""])

        write_range = f"ClanRaffleTickets!A2:B{2 + len(values)}"
        body = {"values": values}

        await self._update_sheet_data(self._sheet_id, write_range, body)
        await self._log_change(changes)

    async def get_absentees(self) -> dict[str, str]:
        """Returns known list of absentees with <rsn:date> format"""
        values = await self._get_sheet_data(self._sheet_id, ABSENCE_RANGE)

        results = {}
        for value in values:
            date = "Unknown"
            if len(value) > 1:
                date = value[1]
            results[value[0]] = date

        return results

    async def shutdown(self):
        async with self._lock:
            logger.info("Closing sheets connection...")
            self._sheets_client.close()


try:
    STORAGE = SheetsStorage.from_account_file("service.json", CONFIG.SHEET_ID)
    logger.info("Connected to spreadsheets api successfully")
except Exception as e:
    logger.critical(e)
    sys.exit(1)
