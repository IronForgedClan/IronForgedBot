from typing import Dict, List, Tuple

import argparse
import os
import sys

import discord
from discord import app_commands
import requests
from common import point_values

from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError


# Don't care about line length for URLs & constants.
# pylint: disable=line-too-long
HISCORES_PLAYER_URL = 'https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={player}'
LEVEL_99_EXPERIENCE = 13034431

SHEETS_SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
# Skip header in read.
SHEET_RANGE = 'ClanIngots!A2:B'
# pylint: enable=line-too-long


def read_dotenv(path: str) -> Dict[str, str]:
    """Read config from a file of k=v entries."""
    config = {}
    with open(path, 'r') as f:
        for line in f:
            tmp = line.partition('=')
            config[tmp[0]] = tmp[2].removesuffix('\n')

    return config


def validate_initial_config(config: Dict[str, str]) -> bool:
    if config.get('SHEETID') is None:
        print('validation failed; SHEETID required but not present in env')
        return False
    if config.get('GUILDID') is None:
        print('validation failed; GUILDID required but not present in env')
        return False
    if config.get('BOT_TOKEN') is None:
        print('validation failed; ' +
              'BOT_TOKEN required but not present in env')
        return False

    return True


def compute_clan_icon(points: int):
    """Determine Icon ID to include in response."""
    if points >= 13000:
        return "Myth"
    if points >= 9000:
        return "Legend"
    if points >= 5000:
        return "Dragon"
    if points >= 3000:
        return "Rune"
    if points >= 1500:
        return "Adamant"
    if points >= 700:
        return "Mithril"
    return "Iron"


class DiscordClient(discord.Client):
    """Client class for bot to handle slashcommands.

    There is a chicken&egg relationship between a discord client & the
    command tree. The tree needs a client during init, but the easiest
    way to upload commands is during client.setup_hook. So, initialize
    the client first, then the tree, then add the tree property before
    calling client.run.

    intents = discord.Intents.default()
    guild = discord.Object(id=$ID)
    client = DiscordClient(intents=intents, upload=true, guild=guild)
    tree = BuildCommandTree(client)
    client.tree = tree

    client.run('token')

    Attributes:
        upload: Whether or not to upload commands to guild.
        guild: Guild for this client to upload commands to.
        tree: CommandTree to use for uploading commands.
    """
    def __init__(
        self, *, intents: discord.Intents, upload: bool,
        guild: discord.Object):
        super().__init__(intents=intents)
        self.upload=upload
        self.guild=guild

    @property
    def tree(self):
        return self._tree

    @tree.setter
    def tree(self, value: app_commands.CommandTree):
        self._tree = value

    async def setup_hook(self):
        # Copy commands to the guild (Discord server)
        # TODO: Move this to a separate CLI solely for uploading commands.
        if self.upload:
            self._tree.copy_global_to(guild=self.guild)
            await self._tree.sync(guild=self.guild)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')


# TODO: Add tests using built command tree.


def build_command_tree(
      client: discord.Client,
      breakdown_dir_path: str,
      sheets_client: Resource,
      sheet_id: str) -> app_commands.CommandTree:
    """Build slashcommand handlers into CommandTree.

    Discord.py's CommandTree object is difficult to interact with. The
    primary documented method to add commands is by using the
    @instance.command decorator.

    Since it needs to call an already instantiated object, we have two
    options:
    - Create a global instantiation and add top level functions.
    - Create a builder function with sub-functions for business logic.

    Since global variables should be wholly avoided wherever possible, we
    opt for the latter pattern.

    Args:
        client: Already instantiated discord.Client object
        breakdown_dir_path: Directory to store temporary point breakdown
            files before uploading to discord.

    Returns:
        app_commands.CommandTree ready to be set as the tree property in
            DiscordClient.
    """
    tree = discord.app_commands.CommandTree(client)

    # NOTE: Python is slow. There is an error case where if the bot takes longer
    # than 3 seconds to respond, Discord won't accept the message.
    # this has a simple solution of responding with
    # interaction.response.send_message early, then sending the real content
    # later with interaction.followup.send. But this makes two messages appear in
    # chat, so we'll do that later if needed.

    @tree.command()
    @app_commands.describe(
        player='Runescape username to compute clan score for.')
    async def score(
        interaction: discord.Interaction, player: str):
        """Compute clan score for a Runescape player name."""
        # TODO: Fail early if the player is not found.
        # TODO: Fail early if username is longer than 12 chars.
        resp = requests.get(HISCORES_PLAYER_URL.format(player=player),
                            timeout=15)
        # Omit the first line of the response, which is total level & xp.
        lines = resp.text.split('\n')[1:]

        # TODO: Include emoji icon from computeIconID in response.
        await interaction.response.send_message(do_score(player, lines))


    @tree.command()
    @app_commands.describe(
        player='Runescape username to break down clan score for.')
    async def breakdown(interaction: discord.Interaction, player: str):
        """Compute player score with complete source enumeration."""
        # TODO: Fail early if the player is not found.
        # TODO: Fail early if username is longer than 12 chars.
        resp = requests.get(HISCORES_PLAYER_URL.format(player=player),
                            timeout=15)
        # Omit the first line of the response, which is total level & xp.
        lines = resp.text.split('\n')[1:]

        message, output = do_breakdown(player, lines)
        # Now we have all of the data that we need for a full point breakdown.
        # If we write a single file though, there is a potential race
        # condition if multiple users try to run breakdown at once.
        # text files are cheap - use the player name as a good-enough amount
        # of uniquity.
        path = os.path.join(breakdown_dir_path, '{}.txt'.format(player))
        with open(path, 'w') as f:
            f.write(output)

        with open(path, 'rb') as f:
            discord_file = discord.File(f, filename='breakdown.txt')
            await interaction.response.send_message(
                message, file=discord_file)


    # TODO: Move ingot implementations & helpers into their own module.


    @tree.command()
    @app_commands.describe(
        player='Runescape username to view ingot count for.')
    async def ingots(interaction: discord.Interaction, player: str):
        """View ingots for a Runescape playername."""
        result = {}

        try:
            result = sheets_client.spreadsheets().values().get(
                spreadsheetId=sheet_id, range=SHEET_RANGE).execute()
        except HttpError as e:
            await interaction.response.send_message(
                f'Encountered error reading from sheets: {e}')
            return

        values = result.get('values', [])

        # Response is a list of lists, all of which have 2
        # entries: ['username', count]. Transform that into
        # a dictionary.
        ingots_by_player = {}
        for i in values:
            ingots_by_player[i[0]] = i[1]

        ingots = ingots_by_player.get(player, 0)
        # TODO: Include ingot emoji in response.
        await interaction.response.send_message(
            f'{player} has {ingots} ingots')


    @tree.command()
    @app_commands.describe(
        player='Runescape username to add ingots to.',
        ingots='Number of ingots to add.')
    async def addingots(
        interaction: discord.Interaction, player: str, ingots: int):
        """Add ingots to a Runescape alias."""
        result = {}

        try:
            result = sheets_client.spreadsheets().values().get(
                spreadsheetId=sheet_id, range=SHEET_RANGE).execute()
        except HttpError as e:
            await interaction.response.send_message(
                f'Encountered error reading from sheets: {e}')
            return

        values = result.get('values', [])

        # Start at 2 since we skip header
        rowIndex = 2
        found = False
        newValue = 0
        for i in values:
            if i[0] == player:
                found = True
                newValue = int(i[1]) + ingots
                break
            rowIndex += 1

        if not found:
            await interaction.response.send_message(
                f'{player} wasn\'t found.')
            return

        range = f'ClanIngots!B{rowIndex}:B{rowIndex}'
        body = {
            'values': [[newValue]]
        }

        try:
            _ = sheets_client.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=range,
                valueInputOption="RAW", body=body).execute()
        except HttpError as e:
            await interaction.response.send_message(
                f'Encountered error writing to sheets: {e}')
            return

        await interaction.response.send_message(
            f'Added {ingots} ingots to {player}')


    @tree.command()
    @app_commands.describe(
        player='Runescape username to set ingots for.',
        ingots='New number of ingots for player.')
    async def updateingots(
        interaction: discord.Interaction, player: str, ingots: int):
        """Set ingots for a Runescape alias."""
        result = {}

        try:
            result = sheets_client.spreadsheets().values().get(
                spreadsheetId=sheet_id, range=SHEET_RANGE).execute()
        except HttpError as e:
            await interaction.response.send_message(
                f'Encountered error reading from sheets: {e}')
            return

        values = result.get('values', [])

        # Start at 2 since we skip header
        rowIndex = 2
        found = False
        for i in values:
            if i[0] == player:
                found = True
                break
            rowIndex += 1

        if not found:
            await interaction.response.send_message(
                f'{player} wasn\'t found.')
            return

        range = f'ClanIngots!B{rowIndex}:B{rowIndex}'
        body = {
            'values': [[ingots]]
        }

        try:
            _ = sheets_client.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=range,
                valueInputOption="RAW", body=body).execute()
        except HttpError as e:
            await interaction.response.send_message(
                f'Encountered error writing to sheets: {e}')
            return

        await interaction.response.send_message(
            f'Set ingot count to {ingots} for {player}')


    return tree


def do_score(player: str, hiscores: List[str]) -> str:
    """Compute score for a Runescape player name.

    Returns string, rather than values, to ensure output
    stability in response to score slashcommand.

    Arguments:
        player: Runescape username.
        hiscores: Response from hiscores already split by
            newlines without total level row.

    Returns:
        Message to respond to Discord with.
    """
    points_by_skill = skill_score(hiscores)
    skill_points = 0
    for _, v in points_by_skill.items():
        skill_points += v

    points_by_activity = activity_score(hiscores)
    activity_points = 0
    for _, v in points_by_activity.items():
        activity_points += v

    points = skill_points + activity_points

    content=f"""{player} has {points}
Points from skills: {skill_points}
Points from minigames & bossing: {activity_points}"""

    return content


def do_breakdown(player: str, hiscores: List[str]) -> Tuple[str, str]:
    """Compute score for a Runescape player with full attribution.

    Returns string, rather than values, to ensure output
    stability in response to breakdown slashcommand.

    Arguments:
        player: Runescape username.
        hiscores: Response from hiscores already split by
            newlines without total level row.

    Returns:
        Message to use in response to Discord;
        Output to be written to txt file & included in
            Discord response.
    """
    points_by_skill = skill_score(hiscores)
    skill_points = 0
    for _, v in points_by_skill.items():
        skill_points += v

    points_by_activity = activity_score(hiscores)
    activity_points = 0
    for _, v in points_by_activity.items():
        activity_points += v

    total_points = skill_points + activity_points

    output = "---Points from Skills---\n"
    for i in point_values.skills():
        if points_by_skill.get(i, 0) > 0:
            output += "{}: {}\n".format(i, points_by_skill.get(i))
    output += "Total Skill Points: {} ({}% of total)\n\n".format(
        skill_points, round((skill_points / total_points) * 100, 2))
    output += "---Points from Minigames & Bossing---\n"
    for i in point_values.activities():
        if points_by_activity.get(i, 0) > 0:
            output += "{}: {}\n".format(i, points_by_activity.get(i))
    output += (
        "Total Minigame & Bossing Points: {} ({}% of total)\n\n".format(
            activity_points, round((activity_points / total_points) * 100, 2)))
    output += "Total Points: {}\n".format(total_points)

    return f"Total Points for {player}: {total_points}\n", output


def skill_score(hiscores: List[str]) -> Dict[str, int]:
    """Compute score from skills portion of hiscores response."""
    score = {}
    skills = point_values.skills()
    for i in range(len(skills)):
        line = hiscores[i].split(',')
        skill = skills[i]
        experience = int(line[2])
        points = 0
        # API response returns -1 if user is not on hiscores.
        if experience >= 0:
            if experience < LEVEL_99_EXPERIENCE:
                points = int(
                    experience / point_values.pre99SkillValue().get(
                        skill, 0))
            else:
                points = int(
                    LEVEL_99_EXPERIENCE /
                    point_values.pre99SkillValue().get(skill, 0)) + int(
                    (experience - LEVEL_99_EXPERIENCE) /
                     point_values.post99SkillValue().get(skill, 0))
        score[skill] = points

    return score


def activity_score(hiscores: List[str]) -> Dict[str, int]:
    """Compute score from activities portion of hiscores response."""
    score = {}
    skills = point_values.skills()
    activities = point_values.activities()
    for i in range(len(activities)):
        line = hiscores[len(skills) + i]
        count = int(line.split(',')[1])
        activity = activities[i]
        if count > 0 and point_values.activityPointValues().get(
                activity, 0) > 0:
            score[activity] = int(
                count / point_values.activityPointValues().get(activity))

    return score


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='A discord bot for Iron Forged.')
    parser.add_argument('--dotenv_path', default='./.env', required=False,
                        help='Filepath for .env with startup k/v pairs.')
    parser.add_argument(
        '--upload_commands', action='store_true',
        help='If supplied, will upload commands to discord server.')
    parser.add_argument(
        '--breakdown_tmp_dir', default='./breakdown_tmp', required=False,
        help='Directory path for where to store point break downs to upload to discord.')
    args = parser.parse_args()


    # Fail out early if our required args are not present.
    init_config = read_dotenv(args.dotenv_path)
    if not validate_initial_config(init_config):
        sys.exit(1)

    # TODO: We lock the bot down with oauth perms; can we shrink intents to match?
    intents = discord.Intents.default()
    guild = discord.Object(id=init_config.get('GUILDID'))
    client = DiscordClient(intents=intents, upload=args.upload_commands,
                           guild=guild)

    creds = service_account.Credentials.from_service_account_file('service.json', scopes=SHEETS_SCOPES)
    service = build('sheets', 'v4', credentials=creds)

    tree = build_command_tree(client, args.breakdown_tmp_dir, service, init_config.get('SHEETID'))
    client.tree = tree

    client.run(init_config.get('BOT_TOKEN'))
