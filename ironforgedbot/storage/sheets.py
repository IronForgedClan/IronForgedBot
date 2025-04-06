import asyncio
import logging
from typing import Any, Iterable
import gspread

from google.oauth2 import service_account
from ironforgedbot.config import CONFIG
from threading import Lock


logging.getLogger("googleapiclient").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


class InvalidWorkbookException(Exception):
    def __init__(self, message="Workbook could not be loaded"):
        self.message = message
        super().__init__(self.message)


class InvalidSheetException(Exception):
    def __init__(self, message="Sheet could not be loaded"):
        self.message = message
        super().__init__(self.message)


class Sheets:
    def __init__(self):
        self.lock: Lock = Lock()
        self.client: gspread.Client | None = None
        self.workbook: gspread.Spreadsheet | None = None

    async def _init_client(self):
        def _setup():
            creds = service_account.Credentials.from_service_account_file(
                "service.json", scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            self.client = gspread.authorize(creds)
            self.workbook = self.client.open_by_key(CONFIG.SHEET_ID)

        async with asyncio.Lock():
            if self.client is None or self.workbook is None:
                await asyncio.to_thread(_setup)

    async def get_sheet(self, sheet_title: str):
        await self._init_client()
        if not self.workbook:
            raise InvalidWorkbookException()
        return await asyncio.to_thread(self.workbook.worksheet, sheet_title)

    async def get_range(self, sheet_title: str, cell_range: str):
        sheet = await self.get_sheet(sheet_title)
        if not sheet:
            raise InvalidSheetException()
        with self.lock:
            return await asyncio.to_thread(sheet.get, cell_range)

    async def update_range(
        self, sheet_title: str, cell_range: str, values: Iterable[Iterable[Any]]
    ):
        sheet = await self.get_sheet(sheet_title)
        if not sheet:
            raise InvalidSheetException()

        with self.lock:
            await asyncio.to_thread(sheet.update, cell_range, values)

    async def update_cell(self, sheet_title: str, row: int, col: int, value: str):
        sheet = await self.get_sheet(sheet_title)
        if not sheet:
            raise InvalidSheetException()
        with self.lock:
            await asyncio.to_thread(sheet.update_cell, row, col, value)

    async def append_row(self, sheet_title: str, values: list):
        sheet = await self.get_sheet(sheet_title)
        if not sheet:
            raise InvalidSheetException()
        with self.lock:
            await asyncio.to_thread(sheet.append_row, values)

    async def get_all_records(self, sheet_title: str):
        sheet = await self.get_sheet(sheet_title)
        if not sheet:
            raise InvalidSheetException()
        with self.lock:
            return await asyncio.to_thread(sheet.get_all_records)
