<h1 align="center">Iron Forged Bot</h1>
<p align="center">
<img alt="Latest Version" src="https://img.shields.io/github/v/tag/IronForgedClan/IronForgedBot?sort=semver&label=version&color=%20%2361ad38">
<a href="https://github.com/IronForgedClan/IronForgedBot/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/IronForgedClan/IronForgedBot"></a>
<a href="https://github.com/psf/black"><img alt="Code style: Black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

<p align="center">A Discord bot for managing the Iron Forged Old School RuneScape clan.</p>

## Commands

| Command               | Parameters                                                                                 | Permission   | Information                                            |
|-----------------------|--------------------------------------------------------------------------------------------|--------------|--------------------------------------------------------|
| `/score`              | Player (str) _Optional_                                                                    | Member       | Returns the score for the player                       |
| `/breakdown`          | Player (str) _Optional_                                                                    | Member       | Returns an interactive breakdown of the player's score |
| `/ingots`             | Player (str) _Optional_                                                                    | Member       | Returns ingot count for player                         |
| `/add_remove_ingots`  | Players (str, comma separated list of player names), Ingots (int), Reason (str)            | Leadership   | Add or remove ingots from one or many players at once  |
| `/raffle_admin`       | Subcommand (str, [start, end, choose_winner])                                              | Leadership   | Parent command for controlling raffle state            |
| `/raffle_tickets`     | N/A                                                                                        | Member       | Returns raffle ticket count for user                   |
| `/buy_raffle_tickets` | Tickets (int)                                                                              | Member       | Purchases raffle tickets for user                      |
| `/sync_members`       | N/A                                                                                        | Leadership   | Synchronises Discord members with storage              |
| `/roster`             | Url (str)                                                                                  | Leadership   | Produces a roster list of players                      |
| `/logs`               | Index (int)                                                                                | Discord Team | Privately shares bot log files                         |
| `/activity_check`     | N/A                                                                                        | Leadership   | Manually starts the activity check automation          |
| `/trick_or_treat`     | N/A                                                                                        | Member       | Holiday special command                                |
| `/debug_commands`     | N/A                                                                                        | -            | Debug tool for testing various commands                |
| `/stress_test`        | N/A                                                                                        | -            | Debug tool for initiating stressful environments       |

## Setup

This setup guide does not go over installing Python, setup of an application within Discord developer portal, or Google Sheets creation; and assumes use of a Linux terminal.

Tested on Arch Linux with Python 3.12.4.

### Virtual Environment

It is recommended to use Python's virtual environments when installing dependencies.

To create a virtual environment for this project, navigate to the project root and run:

``` sh
python -m venv .venv
```

This will create a directory `.venv`. To activate the environment, run:

``` sh
source .venv/bin/activate
```

> [!NOTE]
> You will need to activate the virtual environment every time you start a new shell instance.

### Requirements

The project requirements are listed in `requirements.txt` file. To install, run:

``` sh
pip install -r requirements.txt
```

### Secrets

Secrets are written as key value pairs in the `.env` file.

To create a `.env` file from the example file run:

``` sh
cp .env.example .env
```

Now you can modify the example `.env` file with your values.

> [!WARNING]
> Never check your `.env` file into source control!

#### Keys

| Key                       | Explanation                                                                       |
|---------------------------|-----------------------------------------------------------------------------------|
| ENVIRONMENT               | Defines the environment the bot is running in: 'dev', 'staging', 'prod'           |
| TEMP_DIR                  | The location on disk where temporary files are stored. Default value is `./temp`. |
| SHEET_ID                  | The ID of the Google Sheet.                                                       |
| GUILD_ID                  | The ID of the Discord guild.                                                      |
| BOT_TOKEN                 | The unique token for the application. Found on the Discord Developer Portal.      |
| WOM_API_KEY               | The unique key for connecting to the Wise Old Man API.                            |
| WOM_GROUP_ID              | The unique ID for the clan group on Wise Old Man.                                 |
| AUTOMATION_CHANNEL_ID     | The unique ID of the channel that automation messages will sent.                  |
| TRICK_OR_TREAT_ENABLED    | Boolean flag that determines if the command should be uploaded.                   |
| TRICK_OR_TREAT_CHANNEL_ID | The channel ID where the trick or treat command can be run.                       |


## Running

With everything installed, and in the base directory of the application, the bot can be started with:

``` sh
python main.py
```

To enable uploading of slash commands, you will need to pass the `--upload` argument when starting the bot:

``` sh
python main.py --upload
```

## Logs

The default log level of the application is `INFO`. This can be changed in `ironforgedbot/logging_config.py`.

Logs will output to the console, as well as to rotating files inside the `logs` directory.

## Testing

All test files live within the `tests` directory. The structure within this directory mirrors `ironforgedbot`.

To execute the entire test suite run:

``` sh
python run_tests.py
```

To execute a specific test file, run:

``` sh
python -m unittest tests/path/to/file.py
```

When creating new test files, the filename must follow this pattern `*_test.py`. And the class name must follow this pattern `Test*`.

### Spreadsheets

Go to GCP, in any of your projects, create a new SA -> Manage Keys -> Add -> JSON

Save it as `service.json`

Go to the spreadsheet and share it with the `client_email` from the generated key. 

If it's a fresh GCP project, or you never enabled Google Sheets API, there will be 403 error with the direct link
to enable it. You might need to wait for a few minutes for chances to kick in.

## Data

Upon startup, the bot will attempt to read four files inside the `./data` directory. These files are:

- `data/skills.json`
- `data/bosses.json`
- `data/clues.json`
- `data/raids.json`

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

All contributions must:

- Pass all tests in the test suite.
- Code style must conform to the black formatter.
- If the contribution adds new functionality, tests covering this must also be added.

### Formatting

This codebase uses the [Black](https://github.com/psf/black) formatter. Extensions available for many [popular editors](https://black.readthedocs.io/en/stable/integrations/editors.html). This is enforced through a workflow that runs on all pull requests into main.

>By using Black, you agree to cede control over minutiae of hand-formatting. In return, Black gives you speed, determinism, and freedom from pycodestyle nagging about formatting. You will save time and mental energy for more important matters.
