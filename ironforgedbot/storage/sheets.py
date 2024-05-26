"""An implementation of IronForgedStorage backed by Google Sheets."""

from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
import logging
from pytz import timezone
from typing import Dict, List, Optional, Union

from ironforgedbot.storage.types import IngotsStorage, Member, StorageError

SHEETS_SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
# Skip header in read.
SHEET_RANGE = 'ClanIngots!A2:B'
SHEET_RANGE_WITH_DISCORD_IDS = 'ClanIngots!A2:C'
RAFFLE_RANGE = 'ClanRaffle!A2'
RAFFLE_TICKETS_RANGE = 'ClanRaffleTickets!A2:B'
CHANGELOG_RANGE = 'ChangeLog!A2:F'
ABSENCE_RANGE = 'AbsenceNotice!A2:C'


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

    def read_raffle(self) -> bool:
        """Reads if a raffle is currently ongoing."""
        result = {}
        try:
            result = self._sheets_client.spreadsheets().values().get(
                    spreadsheetId=self._sheet_id,
                    range=RAFFLE_RANGE).execute()
        except HttpError as e:
            raise StorageError(
                    f'Encountered error reading ClanRaffle from sheets: {e}')

        values = result.get('values', [])
        if len(values) < 1:
            return False
        if len(values[0]) < 1:
            return False
        if values[0][0] != 'True':
            return False
        return True

    def start_raffle(self, attribution: str) -> None:
        """Starts a raffle, enabling purchase of raffle tickets."""
        tz = timezone('EST')
        dt = self._clock.now(tz)
        modification_timestamp = dt.strftime('%m/%d/%Y, %H:%M:%S')

        if self.read_raffle():
            raise StorageError('There is already a raffle ongoing')

        body = {'values': [['True']]}

        try:
            _ = self._sheets_client.spreadsheets().values().update(
                    spreadsheetId=self._sheet_id, range=RAFFLE_RANGE,
                    valueInputOption="RAW", body=body).execute()
        except HttpError as e:
            raise StorageError(
                    f'Encountered error writing to sheets: {e}')

        changes = [['', modification_timestamp, 'False', 'True', attribution, 'Started Raffle']]

        try:
            self._log_change(changes)
        except HttpError as e:
            # Just swallow the error; the action is done & captured in version
            # history at least.
            pass

    def end_raffle(self, attribution: str) -> None:
        """Marks a raffle as over, disallowing purchase of tickets."""
        tz = timezone('EST')
        dt = self._clock.now(tz)
        modification_timestamp = dt.strftime('%m/%d/%Y, %H:%M:%S')

        if not self.read_raffle():
            raise StorageError('There is no currently ongoing raffle')

        body = {'values': [['False']]}

        try:
            _ = self._sheets_client.spreadsheets().values().update(
                    spreadsheetId=self._sheet_id, range=RAFFLE_RANGE,
                    valueInputOption="RAW", body=body).execute()
        except HttpError as e:
            raise StorageError(
                    f'Encountered error writing to sheets: {e}')

        changes = [['', modification_timestamp, 'True', 'False', attribution, 'Ended Raffle']]

        try:
            self._log_change(changes)
        except HttpError as e:
            # Just swallow the error; the action is done & captured in version
            # history at least.
            pass

    def read_raffle_tickets(self) -> Dict[int, int]:
        """Reads number of tickets a user has for the current raffle."""
        result = {}
        try:
            result = self._sheets_client.spreadsheets().values().get(
                    spreadsheetId=self._sheet_id,
                    range=RAFFLE_TICKETS_RANGE).execute()
        except HttpError as e:
            raise StorageError(
                    f'Encountered error reading ClanIngots from sheets: {e}')

        # Unlike the ingots table, this is expected to get emptied.
        # So we have to account for an empty response.
        values = result.get('values', [])
        tickets = {}
        for value in values:
            if len(value) >= 2:
                if value[0] == '':
                    continue
                if value[1] == '':
                    value[1] = 0
                tickets[int(value[0])] = int(value[1])

        return tickets

    def add_raffle_tickets(self, member_id: int, tickets: int) -> None:
        """Add tickets to a given member."""
        tz = timezone('EST')
        dt = self._clock.now(tz)
        modification_timestamp = dt.strftime('%m/%d/%Y, %H:%M:%S')
        changes = []

        # If user is in storage, add tickets. Otherwise, add them to storage.
        new_count = tickets
        existing_count = 0
        current_tickets = self.read_raffle_tickets()
        for id, current_count in current_tickets.items():
            if id == member_id:
                existing_count = current_count
                new_count = current_count + tickets

        current_tickets[member_id] = new_count
        changes.append(
                [member_id, modification_timestamp, existing_count, new_count, member_id, 'Bought raffle tickets'])

        # Convert to list for write & sort for stability.
        values = []
        for id, current_count in current_tickets.items():
            values.append([str(id), str(current_count)])

        values.sort(key=lambda x: x[0])

        write_range = f'ClanRaffleTickets!A2:B{2 + len(values)}'
        body = {'values': values}

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

    def delete_raffle_tickets(self, attribution: str) -> None:
        """Deletes all current raffle tickets. Called once when ending a raffle."""
        tz = timezone('EST')
        dt = self._clock.now(tz)
        modification_timestamp = dt.strftime('%m/%d/%Y, %H:%M:%S')
        changes = [['', modification_timestamp, '', '', attribution, 'Cleared all raffle tickets']]

        values = []
        current_tickets = self.read_raffle_tickets()
        for _, _ in current_tickets.items():
            values.append(['', ''])

        write_range = f'ClanRaffleTickets!A2:B{2 + len(values)}'
        body = {'values': values}

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

    def get_absentees(self) -> dict[str:str]:
        """Returns known list of absentees with <rsn:date> format"""
        try:
            result = (self._sheets_client.spreadsheets().values()
                      .get(spreadsheetId=self._sheet_id, range=ABSENCE_RANGE)
                      .execute())
        except HttpError as e:
            raise StorageError(f'Encountered error reading Absentees from sheets: {e}')

        values = result.get('values', [])
        results = {}
        for value in values:
            date = "Unknown"
            if len(value) > 1:
                date = value[1]
            results[value[0]] = date

        return results

    def _log_change(self, changes: List[List[Union[str, int]]]):
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
