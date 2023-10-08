"""An implementation of IronForgedStorage backed by Google Sheets."""

from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
import logging
from pytz import timezone
from typing import List, Optional, Union

from ironforgedbot.storage.types import IngotsStorage, Member, StorageError

SHEETS_SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
# Skip header in read.
SHEET_RANGE = 'ClanIngots!A2:B'
SHEET_RANGE_WITH_DISCORD_IDS = 'ClanIngots!A2:C'
CHANGELOG_RANGE = 'ChangeLog!A2:F'


class SheetsStorage(metaclass=IngotsStorage):
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

    def read_member(self, player: str) -> Optional[Member]:
        """Read member by runescape name."""
        members = self.read_members()

        for member in members:
            if member.runescape_name == player:
                return member

        return None

    def read_members(self) -> List[Member]:
        """Read currently written members."""
        # Then, get all current entries from sheets.
        result = {}
        try:
            result = self._sheets_client.spreadsheets().values().get(
                spreadsheetId=self._sheet_id,
                range=SHEET_RANGE_WITH_DISCORD_IDS).execute()
        except HttpError as e:
            raise StorageError(
                f'Encountered error reading ClanIngots from sheets: {e}')

        values = result.get('values', [])
        members = [Member(id=int(value[2]), runescape_name=value[0], ingots=int(value[1]))
            for value in values]

        return members

    def add_members(self, members: List[Member], attribution: str, note: str = ''):
        """Add new members to sheet."""
        existing = self.read_members()
        existing.extend(members)

        # Sort by RSN for output stability
        existing.sort(key=lambda x: x.runescape_name)

        # We're only adding members, so the length can only increase.
        write_range = f'ClanIngots!A2:C{2 + len(existing)}'
        # string member id or sheets shortens to E notation.
        body = {'values': [
            [member.runescape_name, member.ingots, str(member.id)] for member in existing]}

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
        changes = [
            [member.runescape_name, modification_timestamp, 0, 0, attribution, note]
            for member in members]

        try:
            self._log_change(changes)
        except HttpError as e:
            # Just swallow the error; the action is done & captured in version
            # history at least.
            pass

    def update_members(self, members: List[Member], attribution: str, note: str = ''):
        """Update metadata for existing members."""
        tz = timezone('EST')
        dt = self._clock.now(tz)
        modification_timestamp = dt.strftime('%m/%d/%Y, %H:%M:%S')
        changes = []

        existing = self.read_members()
        for member in members:
            for i, existing_member in enumerate(existing):
                if member.id == existing_member.id:
                    changes.append([existing_member.runescape_name, modification_timestamp,
                        str(existing_member), str(member), attribution, note])
                    existing[i] = member
                    break

        # Sort by RSN for output stability
        existing.sort(key=lambda x: x.runescape_name)

        write_range = f'ClanIngots!A2:C{2 + len(existing)}'
        # string member id or sheets shortens to E notation.
        body = {'values': [
            [member.runescape_name, member.ingots, str(member.id)] for member in existing]}

        try:
            _ = self._sheets_client.spreadsheets().values().update(
                spreadsheetId=self._sheet_id, range=write_range,
                valueInputOption="RAW", body=body).execute()
        except HttpError as e:
            raise StorageError(
                f'Encountered error writing to sheets: {e}')

        try:
            self._log_change(changes)
        except HttpError as e:
            # Just swallow the error; the action is done & captured in version
            # history at least.
            pass

    def remove_members(self, members: List[Member], attribution: str, note: str = ''):
        """Remove members from storage."""
        tz = timezone('EST')
        dt = self._clock.now(tz)
        modification_timestamp = dt.strftime('%m/%d/%Y, %H:%M:%S')
        changes = []

        existing = self.read_members()
        # Removing entries from a list while iterating is very error prone.
        # Make a new list with matching entries.
        remove_ids = [member.id for member in members]
        filtered_values = []
        for member in existing:
            if member.id in remove_ids:
                changes.append(
                    [member.runescape_name, modification_timestamp, str(member),
                    0, attribution, note])
                continue
            filtered_values.append(member)

        # Sort by RSN for output stability.
        filtered_values.sort(key=lambda x: x.runescape_name)
        # string member id or sheets shortens to E notation.
        rows = [[member.runescape_name, member.ingots, str(member.id)]
            for member in filtered_values]
        # Pad empty values to actually remove members from the sheet.
        for _ in range(len(existing) - len(filtered_values)):
            rows.append(['', '', ''])
        write_range = f'ClanIngots!A2:C{2 + len(existing)}'
        body = {'values': rows}

        try:
            _ = self._sheets_client.spreadsheets().values().update(
                spreadsheetId=self._sheet_id, range=write_range,
                valueInputOption="RAW", body=body).execute()
        except HttpError as e:
            raise StorageError(
                f'Encountered error writing to sheets: {e}')

        try:
            self._log_change(changes)
        except HttpError as e:
            # Just swallow the error; the action is done & captured in version
            # history at least.
            pass

    def _log_change(
        self, changes: List[List[Union[str, int]]]):
        """Log change to ChangeLog sheet.

        Arguments:
            changes: Values to prepend to current changelog. Expected
                format: [user, timestamp, old value, new value, mutator, note]

        Raises:
            HttpError: Any error is encountered interacting with sheets.
        """
        body = {'values': changes}

        logging.info(f'wrote changes: {changes}')
        _ = self._sheets_client.spreadsheets().values().append(
            spreadsheetId=self._sheet_id, range=CHANGELOG_RANGE,
            valueInputOption="RAW", body=body).execute()

