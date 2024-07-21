import logging
from typing import List

import discord

from ironforgedbot.common.helpers import normalize_discord_string, reply_with_file
from ironforgedbot.common.ranks import RANKS
from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.roles import extract_roles, find_rank, is_member, is_prospect
from ironforgedbot.storage.types import IngotsStorage, Member


class Signups(object):
    def __init__(self):
        self.ranked = {}
        self.prospects = []
        self.unknowns = []
        self.nick_id_map = {}

    def add_ranked(self, member: discord.Member, rank: RANKS):
        if rank not in self.ranked:
            self.ranked[rank] = []

        nick = normalize_discord_string(member.display_name)
        if nick not in self.ranked:
            self.ranked[rank].append(nick)
            self.nick_id_map[nick] = member.id

    def add_prospect(self, member: discord.Member):
        self.prospects.append(normalize_discord_string(member.display_name))

    def add_unknowns(self, member: discord.Member):
        self.unknowns.append(normalize_discord_string(member.display_name))


async def cmd_roster(
    interaction: discord.Interaction,
    url: str,
    guild: discord.Guild,
    storage: IngotsStorage,
):
    try:
        body = await _calc_roster(url, guild, storage)
    except Exception as e:
        logging.error(f"Roster generation error: {repr(e)}")
        await send_error_response(
            interaction, "An error occurred generating the roster."
        )
        return

    title = f"Roster for the [event]({url})"
    await reply_with_file(title, body, "roster.txt", interaction)


async def _calc_roster(url: str, guild: discord.Guild, storage: IngotsStorage) -> str:
    msg = await _get_message(url, guild)
    signups = await _get_signups(msg)
    result = ""
    members = storage.read_members()

    result += _add_rank(signups, RANKS.IRON, members)
    result += _add_rank(signups, RANKS.MITHRIL, members)
    result += _add_rank(signups, RANKS.ADAMANT, members)
    result += _add_rank(signups, RANKS.RUNE, members)
    result += _add_rank(signups, RANKS.DRAGON, members)
    result += _add_rank(signups, RANKS.LEGEND, members)
    result += _add_rank(signups, RANKS.MYTH, members)

    result += _add_list("Prospects", signups.prospects)
    result += _add_list("Unknown", signups.unknowns)

    return result


def _add_rank(signups: Signups, rank: RANKS, members: List[Member]) -> str:
    if rank not in signups.ranked:
        return ""

    res = f"{str(rank)} rank ({len(signups.ranked[rank])}):\n"
    for ranked in signups.ranked[rank]:
        res += (
            f"{ranked}, ingots: {_get_ingots(signups.nick_id_map[ranked], members)}\n"
        )

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


async def _get_signups(msg: discord.Message) -> Signups:
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
            res.add_prospect(user)
            continue

        rank = find_rank(member_roles)
        if rank is None:
            rank = RANKS.IRON

        res.add_ranked(user, rank)

    return res
