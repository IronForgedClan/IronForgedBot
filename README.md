# IronForgedBot
A bot for managing clan rankings and ingots in the Iron Forged Runescape Clan.

Notable features:

*  Runs Runescape usernames through our own scoring algorithm, returning
a score and rank.
*  Manages per-member "ingots", a currency for buying Discord fun ranks.

All features are implemented via Discord slashcommands.

All documentation assumes a Debian Linux terminal. This may work on other OS',
but YMMV.

## Setup

Main dependencies:

*  python 3.8 or higher (`sudo apt-get install python3`)
*  python3 pip (`sudo apt-get install python3-pip`)
*  The Rapptz/discord.py library (`python3 -m pip install -U discord.py`)
*  Parameterized for testing (`python3 -m pip install parameterized`)

Secrets & tokens are written manually to ".env" in the base app directory.
These are written as key:value pairs separated by "=". Required secrets:

*  GUILDID: The integer of the Discord server the bot will join.
*  BOT_TOKEN: The unique token for your application bot from the Discord
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

There are two main ways to test:

*  Attaching to a personal Discord server, performing the full setup &
   uploading the commands. This has some expensive setup, but will test the
   entire system.
*  `python3 -m unittest main_test.py` will run unit tests.

## Contributing

Codebase follows Google Python Style Guide. This is loosely enforced via
pylint.
