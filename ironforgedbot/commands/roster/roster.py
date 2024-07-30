import logging
from typing import List

import discord

from ironforgedbot.commands.hiscore.calculator import get_rank
from ironforgedbot.common.helpers import (
    normalize_discord_string,
    reply_with_file,
    validate_protected_request,
)
from ironforgedbot.common.ranks import RANKS
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import (
    ROLES,
    extract_roles,
    find_rank,
    is_member,
    is_prospect,
)
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import IngotsStorage, Member

logger = logging.getLogger(__name__)


class Ranked(object):
    def __init__(self, name: str, prospect: bool, ingots: str):
        self.name = name
        self.prospect = prospect
        self.ingots = ingots

    def to_string(self):
        if self.prospect:
            return f"{self.name} [prospect], ingots: {self.ingots}\n"

        return f"{self.name}, ingots: {self.ingots}\n"

    def to_string_clean(self):
        return f"{self.name}\n"


class Signups(object):
    def __init__(self):
        self.ranked = {}
        self.known_ranks = {}
        self.unknowns = []
        self.rank_failures = []

    def add_ranked(
        self, member: discord.Member, rank: RANKS, prospect: bool, members: List[Member]
    ):
        if rank not in self.known_ranks:
            self.ranked[rank] = []
            self.known_ranks[rank] = []

        nick = normalize_discord_string(member.nick)
        if nick not in self.known_ranks:
            self.known_ranks[rank].append(nick)
            ranked = Ranked(nick, prospect, _get_ingots(member.id, members))
            self.ranked[rank].append(ranked)

    def add_prospect(self, member: discord.Member, members: List[Member]):
        nick = normalize_discord_string(member.nick)
        try:
            rank = get_rank(nick)
        except RuntimeError:
            self.rank_failures.append(nick)
            return

        self.add_ranked(member, rank, True, members)

    def add_unknowns(self, member: discord.Member):
        self.unknowns.append(normalize_discord_string(member.name))


async def cmd_roster(
    interaction: discord.Interaction,
    url: str,
):
    await interaction.response.defer()

    try:
        validate_protected_request(
            interaction, interaction.user.display_name, ROLES.LEADERSHIP
        )
    except (ReferenceError, ValueError) as error:
        logger.info(
            f"Member '{interaction.user.display_name}' tried using roster but does not have permission"
        )
        await send_error_response(interaction, str(error))
        return

    if not interaction.guild:
        await send_error_response(interaction, "Error accessing guild information")
        return

    try:
        body = await _calc_roster(url, interaction.guild)
    except Exception as e:
        logger.error(f"Roster generation error: {repr(e)}")
        await send_error_response(
            interaction, "An error occurred generating the roster."
        )
        return

    title = f"Roster for the [event]({url})"
    await reply_with_file(title, body, "roster.txt", interaction)


async def _calc_roster(url: str, guild: discord.Guild) -> str:
    msg = await _get_message(url, guild)
    members = STORAGE.read_members()
    signups = await _get_signups(msg, members)
    result = "====STAFF MESSAGE BELOW====\n"

    result += _add_rank(signups, RANKS.MYTH, False)
    result += _add_rank(signups, RANKS.LEGEND, False)
    result += _add_rank(signups, RANKS.DRAGON, False)
    result += _add_rank(signups, RANKS.RUNE, False)
    result += _add_rank(signups, RANKS.ADAMANT, False)
    result += _add_rank(signups, RANKS.MITHRIL, False)
    result += _add_rank(signups, RANKS.IRON, False)

    result += _add_list("Unknown", signups.unknowns)
    result += _add_list("Rank lookup failures", signups.rank_failures)
    result += "====CLEAN MESSAGE BELOW====\n"

    result += _add_rank(signups, RANKS.MYTH, True)
    result += _add_rank(signups, RANKS.LEGEND, True)
    result += _add_rank(signups, RANKS.DRAGON, True)
    result += _add_rank(signups, RANKS.RUNE, True)
    result += _add_rank(signups, RANKS.ADAMANT, True)
    result += _add_rank(signups, RANKS.MITHRIL, True)
    result += _add_rank(signups, RANKS.IRON, True)

    return result


def _add_rank(signups: Signups, rank: RANKS, clean: bool) -> str:
    if rank not in signups.ranked:
        return ""

    res = f"{str(rank)} rank ({len(signups.ranked[rank])}):\n"
    for ranked in signups.ranked[rank]:
        if clean:
            res += ranked.to_string_clean()
        else:
            res += ranked.to_string()

    res += "\n"
    return res


def _add_list(title: str, names: List[str]) -> str:
    if 0 == len(names):
        return ""

    res = f"{title} ({len(names)}):\n"
    for name in names:
        res += f"{name}\n"

    res += "\n"
    return res


def _get_ingots(discord_id: int, members: List[Member]) -> str:
    for member in members:
        if discord_id == member.id:
            return f"{int(member.ingots / 1000)}k"

    return "?"


async def _get_message(url: str, guild: discord.Guild) -> discord.Message:
    link_parts = url.split("/")
    channel_id = int(link_parts[-2])
    msg_id = int(link_parts[-1])
    channel = guild.get_channel(channel_id)
    msg = await channel.fetch_message(msg_id)
    return msg


async def _get_signups(msg: discord.Message, members: List[Member]) -> Signups:
    res = Signups()
    users = []

    for reaction in msg.reactions:
        if reaction.emoji.name == "DWH":
            users = [user async for user in reaction.users()]
            break

    if 0 == len(users):
        raise Exception("No reactions found for the message")

    for user in users:
        member_roles = extract_roles(user)
        if not is_member(member_roles):
            res.add_unknowns(user)
            continue

        if is_prospect(member_roles):
            res.add_prospect(user, members)
            continue

        rank = find_rank(member_roles)
        if rank is None:
            rank = RANKS.IRON

        res.add_ranked(user, rank, False, members)

    return res
