<h1 align="center">Iron Forged Bot</h1>
<p align="center">
<img alt="Latest Version" src="https://img.shields.io/github/v/tag/IronForgedClan/IronForgedBot?sort=semver&label=version&color=%20%2361ad38">
<a href="https://github.com/IronForgedClan/IronForgedBot/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/IronForgedClan/IronForgedBot"></a>
<a href="https://github.com/psf/black"><img alt="Code style: Black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

<p align="center">A Discord bot for managing the Iron Forged Old School RuneScape clan.</p>

## Commands

| Command              | Parameters                                                                      | Permission | Information                                                                      |
| -------------------- | ------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------- |
| `/score`             | Player (str) _Optional_                                                         | Member     | Returns the score for the player                                                 |
| `/breakdown`         | Player (str) _Optional_                                                         | Member     | Returns an interactive breakdown of the player's score                           |
| `/ingots`            | Player (str) _Optional_                                                         | Member     | Returns ingot count for player                                                   |
| `/raffle`            | N/A                                                                             | Member     | Play or manage the raffle                                                        |
| `/trick_or_treat`    | N/A                                                                             | Member     | Holiday special command                                                          |
| `/whois`             | Player (str) _Optional_                                                         | Member     | Returns name history for the specified member                                    |
| `/add_remove_ingots` | Players (str, comma separated list of player names), Ingots (int), Reason (str) | Leadership | Add or remove ingots from one or many players at once                            |
| `/roster`            | Url (str)                                                                       | Leadership | Produces a roster list of players                                                |
| `/get_role_members`  | Role (str)                                                                      | Leadership | Produces a comma separated list of names for all members with the specified role |
| `/admin`             | N/A                                                                             | Leadership | A menu of administrative commands                                                |
| `/debug_commands`    | N/A                                                                             | -          | Debug tool for testing various commands                                          |
| `/stress_test`       | N/A                                                                             | -          | Debug tool for initiating stressful environments                                 |

> [!IMPORTANT]
> Many commands will not work unless members set up their
> [Server Nickname](https://support.discord.com/hc/en-us/articles/219070107-Server-Nicknames)
> to match their OSRS username.

## Setup

This setup guide assumes use of a Linux terminal.

### Clone the repository

Navigate to a location you want to store the project. Then run the following
command to clone this repository to your machine.

```sh
git clone https://github.com/IronForgedClan/IronForgedBot
```

### Docker

This project uses [Docker](https://www.docker.com/) and
[Docker Compose](https://docs.docker.com/compose/) to streamline setup and
deployment.

### Requirements

- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)
- A Discord server you have admin access to
- A [Discord bot token](https://discord.com/developers/applications)
- A valid Google Sheet ID
- A `service.json` file for connecting to Google Sheets

#### Discord

For development, create your own Discord server and dedicated bot instance.

1. In your Discord app, go to User Settings > Advanced and enable "Developer
   Mode"
2. Create a Discord Server
3. In your
   [Discord Developer Portal](https://discord.com/developers/applications),
   click "New Application"
   - In the Settings > OAuth2 section, use the "OAuth2 URL Generator" helper and
     select:
     - Scopes: `bot`, `applications.commands`
     - Bot Permissions: `Administrator`
   - Use the generated invitation URL at the bottom of the page to invite the
     bot to your Discord server
   - Additionally, reference the
     [Discord Developer Documentation](https://discord.com/developers/docs/intro)

#### How to acquire a `service.json` file

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select an existing project.
3. Enable the **Google Sheets API** for your project:
   - Navigate to **APIs & Services > Library**.
   - Search for "Google Sheets API" and enable it.
4. Create a **Service Account**:
   - Go to **APIs & Services > Credentials**.
   - Click **Create Credentials > Service Account**.
   - Fill in the details and create the account.
5. Create and download the JSON key:
   - In the Service Account details, go to the **Keys** tab.
   - Click **Add Key > Create new key**.
   - Choose JSON format and download the file.
6. Rename the downloaded JSON file to `service.json` and place it in the
   project's root directory.

##### Share Your Google Sheet with the Service Account

- Open your Google Sheet.
- Share it with the **client_email** from your `service.json` file with at least
  **Viewer** access.

### Secrets

Secrets are written as key value pairs in the `.env` file.

To create a `.env` file from the example file run:

```sh
cp .env.example .env
```

Now you can modify the example `.env` file with your values.

> [!WARNING]
> Never check your `.env` file into source control!

#### Keys

| Key                             | Explanation                                                                           | Source                                                               |
| ------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| ENVIRONMENT                     | Defines the environment the bot is running in: 'dev', 'staging', 'prod'               |                                                                      |
| TEMP_DIR                        | The location on disk where temporary files are stored. Default value is `./temp`.     |                                                                      |
| SHEET_ID                        | The ID of the Google Sheet, such as `sheets.google.com/spreadsheets/d/SHEET_ID/edit`. | Ask a project admin for a template sheet, then create your own copy. |
| GUILD_ID                        | The ID of the Discord guild.                                                          | Your own Discord server: right click, "Copy Server ID".              |
| BOT_TOKEN                       | The unique token for the application.                                                 | Your own Discord Developer Portal: Applications > Bot > Reset Token. |
| WOM_API_KEY                     | The unique key for connecting to the Wise Old Man API.                                | Ask a project admin.                                                 |
| WOM_GROUP_ID                    | The unique ID for the clan group on Wise Old Man.                                     | Ask a project admin.                                                 |
| AUTOMATION_CHANNEL_ID           | The unique ID of the channel that automation messages will sent.                      | Your own Discord server channel: right click, "Copy Channel ID".     |
| TRICK_OR_TREAT_ENABLED          | Boolean flag that determines if the command should be uploaded.                       | Your own Discord server channel: right click, "Copy Channel ID".     |
| TRICK_OR_TREAT_CHANNEL_ID       | The channel ID where the trick or treat command can be run.                           | Your own Discord server: right click, "Copy Channel ID".             |
| TRICK_OR_TREAT_COOLDOWN_SECONDS | The number of seconds allowed between command executions. Default 3600.               |                                                                      |
| RAFFLE_CHANNEL_ID               | The unique ID of the channel that will house the raffle.                              | Your own Discord server channel: right click, "Copy Channel ID".     |
| DB_ROOT                         | The password used by the root database account.                                       | Generate a secure password.                                          |
| DB_USER                         | The name of the user account the bot will use to access the database.                 | Any value. Eg: test_user                                             |
| DB_PASS                         | The password of the account the bot will use to access the database.                  | Generate a secure password.                                          |
| DB_NAME                         | The name of the database the bot will attempt to connect to.                          | Any value. Eg: bot_test                                              |

### Migrations

You will need to run the database migrations before the bot will be able to use
the database. To do so, you can run the following command. You will need to do
this every time the database schema changes. Migration files live inside the
`alembic/versions` directory.

```sh
make migrate
```

> [!NOTE]\
> There is a chicken and egg issue here where you can't run the project without
> a database and its migrations, but you can't run the migrations without a
> database to talk to. In order to resolve this the first time the project is
> set up, you will need to spin up the initial containers with `make up` before
> continuing to run the migrations. Be warned that you will see errors in the
> output, as we haven't run the migrations yet.

### Running inside Docker

Now everything is ready, you can bring the project online with the following
command.

```sh
make up
```

You should now see in the console the database spinning up, followed by the bot.
The bot should then shortly connect to your Discord server. Voilà.

#### Stopping the project

So you've done some work, and want to pack it in for the day? You can kill the
project by either doing `CTRL+C` twice in the terminal window running the docker
containers. Or with the following command if running detatched.

```sh
make down
```

## Makefile

This project includes a `Makefile` with handy commands to simplify development.
If at any point a `make` command doesn't work, you can open the `Makefile` to
view its source command and try running that instead.

### Commands

- `make up`\
  Starts the containers using `docker compose up`.

- `make down`\
  Stops and removes the containers.

- `make test`\
  Runs the test suite.

- `make format`\
  Formats the codebase using Black formatter.

- `make shell`\
  Opens an interactive bash shell inside the bot container.

- `make migrate`\
  Runs the database migrations.

- `make revision`\
  Creates a new database migration. Expects a `DESC` parameter. Eg:
  `make revision DESC="added a new column to the members table"`

- `make downgrade`\
  Reverts the most recent database migration.

- `make update-deps`\
  Updates all project dependencies to their latest versions and rebuilds the container.

- `make clean`\
  Stops containers, removes project containers and images, and prunes unused Docker resources to free up disk space.

## Tooling

As all dependencies are installed within the Docker container, you might find
your editor complaining it can't find the library referenced in the code. To
aleviate this we can install the project dependencies in the project root so our
tooling can pick them up.

### Virtual Environment

It is recommended to use Python's virtual environments when installing
dependencies.

```sh
python -m venv .venv
```

This will create a directory `.venv`. To activate the environment, run:

```sh
source .venv/bin/activate
```

### Requirements

The project requirements are listed in `requirements.txt` file. To install, run:

```sh
pip install -r requirements.txt
```

## Logs

The default log level of the application is `INFO`. This can be changed in
`ironforgedbot/logging_config.py`.

Logs will output to the console, as well as to rotating files inside the `logs`
directory.

## Testing

All test files live within the `tests` directory. The structure within this
directory mirrors `ironforgedbot`.

To execute the entire test suite run:

```sh
make test
```

When creating new test files, the filename must follow the pattern `*_test.py`.
And the class name must follow the pattern `Test*`.

## Data

Upon startup, the bot will attempt to read four files inside the `./data`
directory. These files are:

- `data/skills.json`
- `data/bosses.json`
- `data/clues.json`
- `data/raids.json`

These files contain information on how the bot will award points, control output
order, and set emojis. They are in `json` format so as to be human readable, and
easy to modify for someone non-technical. Once a file has been changed, the bot
will need to be restarted to load the new values. No code changes necessary.

There are two categories of data files, `Skill` and `Activity`. `skills.json` is
the only `Skill` type, while the others are all types of `Activity`.

All files contain an array `[]` of objects `{}`.

### Skill

A `Skill` file looks something like this:

```json
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

- `name`: This field **must** be identical to the value on the official
  hiscores.
- `display_order`: This is the order in which it is displayed. Currently only
  used in the `breakdown` command.
- `emoji_key`: This is the name of the emoji to use to represent this skill.
- `xp_per_point`: This is the amount of xp required to award one point.
- `xp_per_point_post_99`: This is the amount of xp required to award one point
  beyond level 99.

### Activity

An `Activity` file looks something like this:

```json
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

- `name`: This field **must** be identical to the value on the official
  hiscores.
- `display_name`: This field is optional. It is the text that will be displayed
  for this activity. Currently only used in the `breakdown` command for clues.
- `display_order`: This is the order in which it is displayed. Currently only
  used in the `breakdown` command.
- `emoji_key`: This is the name of the emoji to use to represent this skill.
- `kc_per_point`: This is the number of kill count required to award one point.

## Contributing

Contributions must:

- Address a specific issue by ticket number.
- Pass all tests in the test suite.
- Code style must conform to the black formatter.
- If the contribution adds new functionality, tests covering this must also be
  added.

### Formatting

This codebase uses the [Black](https://github.com/psf/black) formatter.
Extensions available for many
[popular editors](https://black.readthedocs.io/en/stable/integrations/editors.html).
This is enforced through a workflow that runs on all pull requests into main.

> By using Black, you agree to cede control over minutiae of hand-formatting. In
> return, Black gives you speed, determinism, and freedom from pycodestyle
> nagging about formatting. You will save time and mental energy for more
> important matters.
