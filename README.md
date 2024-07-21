# IronForgedBot

A bot for managing clan rankings and ingots in the Iron Forged Runescape Clan.

Notable features:

- Runs Runescape usernames through our own scoring algorithm, returning
  a score and rank.
- Manages per-member "ingots", a currency for buying Discord fun ranks.

All features are implemented via Discord slashcommands.

All documentation assumes a Debian Linux terminal. This may work on other OS',
but YMMV.

## Setup

Main dependencies:

- python 3.8 or higher (`sudo apt-get install python3`)
- python3 pip (`sudo apt-get install python3-pip`)
- The Rapptz/discord.py library (`python3 -m pip install -U discord.py`)
- Parameterized for testing (`python3 -m pip install parameterized`)
- Libraries for connecting to Google Sheets API (`pip install --upgrade
google-api-python-client google-auth-httplib2 google-auth-oauthlib`)

Secrets & tokens are written manually to ".env" in the base app directory.
These are written as key:value pairs separated by "=". Required secrets:

- SHEETID: Unique ID for sheet to connect to.
- GUILDID: The integer of the Discord server the bot will join.
- BOT_TOKEN: The unique token for your application bot from the Discord
  Developer Portal.

You'll also need to add the bot role you create in the developer portal to
your server. In the Developer Portal, under "OAuth2 > URL Generator",
select the "bot" option and fill in the permissions. This will give you a
URL you can go to and add the bot to any servers you have "manage members"
permissions for.

## Running

With everything installed, in the base dir of the application, it can be
launched simply with `python3 main.py`. This will let it handle slashcommands
in the server it is set to join.

To upload new slashcommands to the server: `python3 main.py --upload_commands`.

## Testing

Test files live within the `tests/` directory. There is a script `run_tests.py`
that scans that directory and runs all the unit tests it finds.

All test filenames must follow this pattern: `*_test.py`

There are two main ways to test:

- Attaching to a personal Discord server, performing the full setup &
  uploading the commands. This has some expensive setup, but will test the
  entire system.
- `python3 run_tests.py` will run all unit tests within the project.

You can also run a specific test file directly:
`python3 -m unittest tests/example_test.py`

## Testing spreadsheets locally

Go to GCP, in any of your projects, create a new SA -> Manage Keys -> Add -> JSON

Save it as `service.json`

Go to the spreadsheet and share it with the `client_email` from the generated key. 

If it's a fresh GCP project, or you never enabled Google Sheets API, there will be 403 error with the direct link
to enable it. You might need to wait for a few minutes for chances to kick in.

## Data

Upon startup, the bot will attempt to read four files inside the `/data` directory. These files are:

- `skills.json`
- `bosses.json`
- `clues.json`
- `raids.json`

These files contain information on how the bot will award points, control output order, and set emojis. They are in `json` format so as to be human readable, and easy to modify for someone non-technical. Once a file has been changed, the bot will need to be restarted to load the new values. No code changes necessary.

There are two categories of data files, `Skill` and `Activity`. `skills.json` is the only `Skill` type, while the others are all types of `Activity`.

All files contain an array `[]` of objects `{}`.

### Skill
A `Skill` file looks something like this:

``` json
[
  {
    "name": "Attack",
    "display_order": 1,
    "emoji_key": "Attack",
    "xp_per_point": 100000,
    "xp_per_point_post_99": 300000
  }
]
```

- `name`: This field **must** be identical to the value on the official hiscores.
- `display_order`: This is the order in which it is displayed. Currently only used in the `breakdown` command.
- `emoji_key`: This is the name of the emoji to use to represent this skill.
- `xp_per_point`: This is the amount of xp required to award one point.
- `xp_per_point_post_99`: This is the amount of xp required to award one point beyond level 99.

### Activity
An `Activity` file looks something like this:

``` json
[
  {
    "name": "Clue Scrolls (beginner)",
    "display_name": "Beginner",
    "display_order": 1,
    "emoji_key": "ClueScrolls_Beginner",
    "kc_per_point": 10
  }
]
```

- `name`: This field **must** be identical to the value on the official hiscores.
- `display_name`: This field is optional. It is the text that will be displayed for this activity. Currently only used in the `breakdown` command for clues.
- `display_order`: This is the order in which it is displayed. Currently only used in the `breakdown` command.
- `emoji_key`: This is the name of the emoji to use to represent this skill.
- `kc_per_point`: This is the number of kill count required to award one point.

## Contributing

Codebase follows Google Python Style Guide. This is loosely enforced via
pylint.
