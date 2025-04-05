import asyncio
import logging
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build
from ironforgedbot.event_emitter import event_emitter
from ironforgedbot.config import CONFIG
from ironforgedbot.decorators import retry_on_exception
from ironforgedbot.models.absent_member import AbsentMember

logging.getLogger("googleapiclient").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
ABSENCE_RANGE = "AbsenceNotice!A2:F"


class SheetsStorage:
    def __init__(self, sheets_client: Resource, sheet_id: str):
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
            return result.get("values", [])

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

    async def get_absentees(self) -> list[AbsentMember]:
        """Returns known list of absentees"""
        data = await self._get_sheet_data(self._sheet_id, ABSENCE_RANGE)

        members = []
        for entry in data:
            members.append(
                AbsentMember(
                    entry[0],
                    entry[1],
                    entry[2],
                    entry[3] if len(entry) > 3 else "",
                    entry[4] if len(entry) > 4 else "",
                    entry[5] if len(entry) > 5 else "",
                )
            )

        return members

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

        write_range = f"AbsenceNotice!A2:F{2 + len(values)}"
        await self._update_sheet_data(self._sheet_id, write_range, {"values": values})

    async def shutdown(self):
        async with self._lock:
            logger.info("Closing sheets connection...")
            self._sheets_client.close()


try:
    SHEETS = SheetsStorage.from_account_file("service.json", CONFIG.SHEET_ID)
    logger.info("Connected to spreadsheets api successfully")
except Exception as e:
    logger.critical(e)
    sys.exit(1)
