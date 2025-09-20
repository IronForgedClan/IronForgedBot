import unittest
from unittest.mock import AsyncMock, Mock, patch

from ironforgedbot.storage.sheets import (
    InvalidSheetException,
    InvalidWorkbookException,
    Sheets,
)


class SheetsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sheets = Sheets()
        self.mock_client = Mock()
        self.mock_workbook = Mock()
        self.mock_sheet = Mock()

    @patch.object(Sheets, 'get_sheet')
    async def test_get_range_success(self, mock_get_sheet):
        test_data = [["data1", "data2"], ["data3", "data4"]]
        mock_get_sheet.return_value = self.mock_sheet
        
        with patch("ironforgedbot.storage.sheets.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = test_data
            
            result = await self.sheets.get_range("test_sheet", "A1:B2")
            
            self.assertEqual(result, test_data)
            mock_get_sheet.assert_called_once_with("test_sheet")

    @patch.object(Sheets, 'get_sheet')
    async def test_get_range_raises_exception_when_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None
        
        with self.assertRaises(InvalidSheetException):
            await self.sheets.get_range("test_sheet", "A1:B2")

    @patch.object(Sheets, 'get_sheet')
    async def test_update_range_success(self, mock_get_sheet):
        test_values = [["new1", "new2"], ["new3", "new4"]]
        mock_get_sheet.return_value = self.mock_sheet
        
        with patch("ironforgedbot.storage.sheets.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = None
            
            await self.sheets.update_range("test_sheet", "A1:B2", test_values)
            
            mock_get_sheet.assert_called_once_with("test_sheet")

    @patch.object(Sheets, 'get_sheet')
    async def test_update_range_raises_exception_when_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None
        
        with self.assertRaises(InvalidSheetException):
            await self.sheets.update_range("test_sheet", "A1:B2", [["data"]])

    @patch.object(Sheets, 'get_sheet')
    async def test_update_cell_success(self, mock_get_sheet):
        mock_get_sheet.return_value = self.mock_sheet
        
        with patch("ironforgedbot.storage.sheets.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = None
            
            await self.sheets.update_cell("test_sheet", 1, 1, "new_value")
            
            mock_get_sheet.assert_called_once_with("test_sheet")

    @patch.object(Sheets, 'get_sheet')
    async def test_update_cell_raises_exception_when_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None
        
        with self.assertRaises(InvalidSheetException):
            await self.sheets.update_cell("test_sheet", 1, 1, "value")

    @patch.object(Sheets, 'get_sheet')
    async def test_append_row_success(self, mock_get_sheet):
        test_values = ["value1", "value2", "value3"]
        mock_get_sheet.return_value = self.mock_sheet
        
        with patch("ironforgedbot.storage.sheets.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = None
            
            await self.sheets.append_row("test_sheet", test_values)
            
            mock_get_sheet.assert_called_once_with("test_sheet")

    @patch.object(Sheets, 'get_sheet')
    async def test_append_row_raises_exception_when_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None
        
        with self.assertRaises(InvalidSheetException):
            await self.sheets.append_row("test_sheet", ["data"])

    @patch.object(Sheets, 'get_sheet')
    async def test_get_all_records_success(self, mock_get_sheet):
        test_records = [{"name": "test1", "value": "value1"}, {"name": "test2", "value": "value2"}]
        mock_get_sheet.return_value = self.mock_sheet
        
        with patch("ironforgedbot.storage.sheets.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = test_records
            
            result = await self.sheets.get_all_records("test_sheet")
            
            self.assertEqual(result, test_records)
            mock_get_sheet.assert_called_once_with("test_sheet")

    @patch.object(Sheets, 'get_sheet')
    async def test_get_all_records_raises_exception_when_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None
        
        with self.assertRaises(InvalidSheetException):
            await self.sheets.get_all_records("test_sheet")

    @patch("ironforgedbot.storage.sheets.asyncio.to_thread")
    async def test_get_sheet_success(self, mock_to_thread):
        self.sheets.workbook = self.mock_workbook
        mock_to_thread.return_value = self.mock_sheet

        result = await self.sheets.get_sheet("test_sheet")

        self.assertEqual(result, self.mock_sheet)
        mock_to_thread.assert_called_with(self.mock_workbook.worksheet, "test_sheet")

    async def test_get_sheet_raises_exception_when_no_workbook(self):
        with patch.object(self.sheets, '_init_client', new_callable=AsyncMock):
            self.sheets.workbook = None

            with self.assertRaises(InvalidWorkbookException):
                await self.sheets.get_sheet("test_sheet")

    @patch("ironforgedbot.storage.sheets.CONFIG")
    @patch("ironforgedbot.storage.sheets.service_account")
    @patch("ironforgedbot.storage.sheets.gspread")
    @patch("ironforgedbot.storage.sheets.asyncio.to_thread")
    async def test_init_client_creates_client_and_workbook(self, mock_to_thread, mock_gspread, mock_service_account, mock_config):
        mock_config.SHEET_ID = "test_sheet_id"
        self.sheets.client = None
        self.sheets.workbook = None
        
        mock_creds = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = mock_creds
        mock_gspread.authorize.return_value = self.mock_client
        self.mock_client.open_by_key.return_value = self.mock_workbook
        
        def mock_setup():
            pass
            
        mock_to_thread.return_value = None
        
        await self.sheets._init_client()
        
        mock_to_thread.assert_called_once()

    @patch("ironforgedbot.storage.sheets.asyncio.to_thread")
    async def test_init_client_skips_when_already_initialized(self, mock_to_thread):
        self.sheets.client = self.mock_client
        self.sheets.workbook = self.mock_workbook

        await self.sheets._init_client()

        mock_to_thread.assert_not_called()

    async def test_client_initialization_uses_asyncio_lock(self):
        with patch("ironforgedbot.storage.sheets.asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = None
            self.sheets.client = None
            self.sheets.workbook = None

            await self.sheets._init_client()

            mock_to_thread.assert_called_once()