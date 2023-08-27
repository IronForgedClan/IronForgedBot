"""An implementation of IronForgedStorage backed by Google Sheets."""

from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from ironforgedbot.storage.types import IronForgedStorage, Member, StorageError

SHEETS_SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
# Skip header in read.
SHEET_RANGE = 'ClanIngots!A2:B'
SHEET_RANGE_WITH_DISCORD_IDS = 'ClanIngots!A2:C'
CHANGELOG_RANGE = 'ChangeLog!A2:F'


class SheetsStorage(metaclass=IronForgedStorage):
    """A storage implementation backed by Sheets.

    Expected schema is a sheet with two tabs:
        ClanIngots: RSN, ingots, Discord ID
        ChangeLog: Timestamp (EST), previous value, new value,
            update reason, manual note.
    """

    def __init__(
        self,
        sheets_client: Resource,
        sheet_id: str,
        clock: datetime = None):
        """Init.

        Arguments:
            sheets_client: Built Resource object to interact with
                sheets API.
            sheet_id: ID of sheets to connect to.
        """
        self._sheets_client = sheets_client
        self._sheet_id = sheet_id
        if clock is None:
            self._clock = datetime
        else:
            self._clock = clock

    @classmethod
    def from_account_file(
        cls,
        account_filepath: str,
        sheet_id: str) -> 'SheetsStorage':
        """Build sheets Resource from service account file."""
        creds = service_account.Credentials.from_service_account_file(
            account_filepath, scopes=SHEETS_SCOPES)
        service = build('sheets', 'v4', credentials=creds)

        return cls(service, sheet_id)

    def read_ingots(self, player: str) -> int:
        """Reads current ingots based on Runescape name."""
        try:
            result = self._sheets_client.spreadsheets().values().get(
                spreadsheetId=self._sheet_id, range=SHEET_RANGE).execute()
        except HttpError as e:
            raise StorageError(f'Error reading from sheets: {e}')

        values = result.get('values', [])

        # Response is a list of lists, all of which have 2
        # entries: ['username', count]. Transform that into
        # a dictionary.
        ingots_by_player = {}
        for i in values:
            ingots_by_player[i[0]] = i[1]

        return int(ingots_by_player.get(player, 0))

    def adjust_ingots(self, player: str, ingots: str, caller: str) -> None:
        """Adjust player's ingots by provided amount."""
        result = {}
        try:
            result = self._sheets_client.spreadsheets().values().get(
                spreadsheetId=self._sheet_id, range=SHEET_RANGE).execute()
        except HttpError as e:
            raise StorageError(f'Error reading from sheets: {e}')

        values = result.get('values', [])

        # Start at 2 since we skip header
        row_index = 2
        found = False
        new_value = 0
        old_value = 0
        for i in values:
            if i[0] == player:
                found = True
                old_value = int(i[1])
                new_value = int(i[1]) + ingots
                break
            row_index += 1

        if not found:
            raise StorageError(f'{player} wasn\'t found.')

        write_range = f'ClanIngots!B{row_index}:B{row_index}'
        body = {'values': [[new_value]]}

        try:
            _ = self._sheets_client.spreadsheets().values().update(
                spreadsheetId=self._sheet_id, range=write_range,
                valueInputOption="RAW", body=body).execute()
        except HttpError as e:
            raise StorageError(
                f'Encountered error writing to sheets: {e}')

        tz = timezone('EST')
        dt = self._clock.now(tz)
        modification_timestamp = dt.strftime('%m/%d/%Y, %H:%M:%S')
        change = [[player, modification_timestamp, old_value, new_value, caller, '']]

        try:
            self._log_change(change)
        except HttpError as e:
            # Just swallow the error; the action is done & captured in version
            # history at least.
            pass

    def update_ingots(self, player: str, ingots: int, caller: str):
        """Overwrite ingots for a player with a new value."""
        result = {}
        try:
            result = self._sheets_client.spreadsheets().values().get(
                spreadsheetId=self._sheet_id, range=SHEET_RANGE).execute()
        except HttpError as e:
            raise StorageError(f'Error reading from sheets: {e}')

        values = result.get('values', [])

        # Start at 2 since we skip header
        row_index = 2
        found = False
        old_value = 0
        for i in values:
            if i[0] == player:
                found = True
                old_value = i[1]
                break
            row_index += 1

        if not found:
            raise StorageError(f'{player} wasn\'t found.')

        write_range = f'ClanIngots!B{row_index}:B{row_index}'
        body = {'values': [[ingots]]}

        try:
            _ = self._sheets_client.spreadsheets().values().update(
                spreadsheetId=self._sheet_id, range=write_range,
                valueInputOption="RAW", body=body).execute()
        except HttpError as e:
            raise StorageError(
                f'Encountered error writing to sheets: {e}')

        tz = timezone('EST')
        dt = self._clock.now(tz)
        modification_timestamp = dt.strftime('%m/%d/%Y, %H:%M:%S')
        change = [[player, modification_timestamp, old_value, ingots, caller, '']]

        try:
            self._log_change(change)
        except HttpError as e:
            # Just swallow the error; the action is done & captured in version
            # history at least.
            pass

    # TODO: Implement these.
    def read_members(self) -> List[Member]:
        raise NotImplementedError

    def add_members(self, members: List[Member], caller: str):
        raise NotImplementedError

    def update_members(self, members: List[Member], caller: str):
        raise NotImplementedError

    def remove_members(self, members: List[Member], caller: str):
        raise NotImplementedError

    # TODO: We should also log to a logfile in case this function fails.
    # Since we tuck this behind an interface, we don't want to surface this to users.
    def _log_change(
        self, changes: List[List[Union[str, int]]]):
        """Log change to ChangeLog sheet.

        Arguments:
            changes: Values to prepend to current changelog. Expected
                format: [user, timestamp, old value, new value, mutator, note]

        Raises:
            HttpError: Any error is encountered interacting with sheets.
        """
        changelog_response = self._sheets_client.spreadsheets().values().get(
                spreadsheetId=self._sheet_id,
                range=CHANGELOG_RANGE).execute()

        # We want newest changes first
        changelog_values = changelog_response.get('values', [])
        changes.extend(changelog_values)

        change_range = f'ChangeLog!A2:F{2 + len(changes)}'
        body = {'values': changes}

        _ = self._sheets_client.spreadsheets().values().update(
            spreadsheetId=self._sheet_id, range=change_range,
            valueInputOption="RAW", body=body).execute()

