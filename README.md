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

### Set up SSH authentication with GitHub

This project uses a private submodule that requires SSH authentication.

> [!IMPORTANT]
> You must set up SSH keys with GitHub before cloning. HTTPS will not work for
> the private submodule.

#### Generate SSH key (if you don't have one)

```sh
ssh-keygen -t ed25519 -C "your_email@example.com"
# Press Enter to accept default location
# Optionally enter a passphrase
```

#### Add SSH key to ssh-agent

```sh
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

#### Add SSH key to GitHub

1. Copy your public key:
   ```sh
   cat ~/.ssh/id_ed25519.pub
   ```
2. Go to GitHub → Settings → SSH and GPG keys → New SSH key
3. Paste your public key and save

#### Test your connection

```sh
ssh -T git@github.com
# Should respond: "Hi username! You've successfully authenticated..."
```

For more details, see
[GitHub's SSH documentation](https://docs.github.com/en/authentication/connecting-to-github-with-ssh).

### Clone the repository

Navigate to a location you want to store the project. Then run the following
command to clone this repository to your machine.

```sh
git clone git@github.com:IronForgedClan/IronForgedBot.git
```

### Initialize Data Submodule

This project uses a private git submodule for data files.

> [!IMPORTANT]
> You'll need access to the `IronForgedBot_Data` private repository. Contact
> repository maintainers if you don't have access.

#### First-time setup (after cloning)

```sh
# Initialize and fetch the submodule
git submodule init
git submodule update
```

#### Or clone with submodules in one step

```sh
git clone --recurse-submodules git@github.com:IronForgedClan/IronForgedBot.git
```

#### Updating data files

```sh
# Using make command
make update-data

# Or manually
git submodule update --remote data
```

> [!NOTE]
> If you see errors about missing `data/*.json` files, ensure the submodule is
> initialized using the commands above.

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
| INGOT_SHOP_CHANNEL_ID           | The unique ID of the ingot shop channel.                                              | Your own Discord server channel: right click, "Copy Channel ID".     |
| RULES_CHANNEL_ID                | The unique ID of the rules channel.                                                   | Your own Discord server channel: right click, "Copy Channel ID".     |
| DB_ROOT                         | The password used by the root database account.                                       | Generate a secure password.                                          |
| DB_USER                         | The name of the user account the bot will use to access the database.                 | Any value. Eg: test_user                                             |
| DB_PASS                         | The password of the account the bot will use to access the database.                  | Generate a secure password.                                          |
| DB_NAME                         | The name of the database the bot will attempt to connect to.                          | Any value. Eg: bot_test                                              |
| LOG_LEVEL                       | File handler log level. Default: `INFO`.                                              | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`                      |
| LOG_CONSOLE_LEVEL               | Console log level (overrides environment-based default).                              | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`                      |
| LOG_DIR                         | Directory for log files. Default: `./logs`.                                           | Any valid directory path.                                            |
| LOG_FILE_MAX_BYTES              | Max size of each log file before rotation. Default: `10000000` (10MB).                | Integer (bytes).                                                     |
| LOG_FILE_BACKUP_COUNT           | Number of backup log files to keep. Default: `10`.                                    | Integer.                                                             |
| LOG_JSON_FORMAT                 | Use JSON formatting for logs. Default: `false`.                                       | `true`, `false`                                                      |
| CRON_SYNC_MEMBERS               | Member sync schedule. Default: `50 3,15 * * *` (3:50 and 15:50 UTC daily)             | Standard cron format: "minute hour day month day_of_week"            |
| CRON_REFRESH_RANKS              | Rank refresh schedule. Default: `10 4,16 * * *` (4:10 and 16:10 UTC daily)            | Standard cron format                                                 |
| CRON_CHECK_ACTIVITY             | Activity check schedule. Default: `0 1 * * 1` (Monday 1:00 UTC)                       | Standard cron format                                                 |
| CRON_CHECK_DISCREPANCIES        | Discrepancy check schedule. Default: `0 0 * * 0` (Sunday 0:00 UTC)                    | Standard cron format                                                 |
| CRON_CLEAR_CACHES               | Cache cleanup schedule. Default: `*/10 * * * *` (every 10 minutes)                    | Standard cron format                                                 |
| CRON_PAYROLL                    | Monthly payroll schedule. Default: `0 6 1 * *` (1st of month at 6:00 UTC)             | Standard cron format                                                 |

> [!NOTE]
> All scheduled jobs run in UTC timezone. Cron schedules use standard cron expression format: "minute hour day_of_month month day_of_week".
> Day of week: 0=Sunday, 1=Monday, etc. For syntax details, see [Cron format](https://en.wikipedia.org/wiki/Cron).

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
  Updates all project dependencies to their latest versions and rebuilds the
  container.

- `make update-data`\
  Updates the data submodule to the latest commit from the private repository.

- `make clean`\
  Stops containers, removes project containers and images, and prunes unused
  Docker resources to free up disk space.

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

Logs output to both the console and rotating files inside the `logs` directory.

### Configuration

Log behavior can be configured via environment variables in `.env`:

- **File Logs**: Controlled by `LOG_LEVEL` (default: `INFO`)
- **Console Logs**: Controlled by `LOG_CONSOLE_LEVEL` or automatically set based
  on `ENVIRONMENT`:
  - `dev` -> `DEBUG`
  - `staging` -> `INFO`
  - `prod` -> `WARNING`

See the [Keys](#keys) section for all available log configuration options.

### Log Files

Log files are named `bot_{ENVIRONMENT}.log` and stored in the directory
specified by `LOG_DIR` (default: `./logs`). Files rotate when they reach
`LOG_FILE_MAX_BYTES` in size, keeping `LOG_FILE_BACKUP_COUNT` backups.

## Testing

All test files live within the `tests` directory. The structure within this
directory mirrors `ironforgedbot`.

To execute the entire test suite run:

```sh
make test
```

When creating new test files, the filename must follow the pattern `*_test.py`.
And the class name must follow the pattern `Test*`.

## Data Files

The bot uses JSON data files to configure:

- **OSRS Skills** (`skills.json`) - XP-per-point values and display settings
- **Boss Activities** (`bosses.json`) - KC-per-point values for boss encounters
- **Clue Scrolls** (`clues.json`) - KC-per-point values for clue tiers
- **Raids** (`raids.json`) - KC-per-point values for raid activities
- **Seasonal Events** (`trick_or_treat.json`) - Event content and mechanics

These files control point calculation, display order, and emoji mappings.
Changes to these files require a bot restart but no code changes.

> [!NOTE]
> For detailed schema documentation and editing instructions, see the
> [IronForgedBot_Data repository README](https://github.com/IronForgedClan/IronForgedBot_Data).

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
