import gspread
from oauth2client.service_account import ServiceAccountCredentials


def get_sheet_data(sheet_name, worksheet_name):
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


def import_membes(sheet_data):
    for row in sheet_data:
        print(row)


def main():
    sheet_members = get_sheet_data("IronForged_bot_test", "ClanIngots")

    import_membes(sheet_members)


if __name__ == "__main__":
    main()
