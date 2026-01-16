#!/usr/bin/env python3
import os
import sys

# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import discord
import asyncio
import argparse
from collections import Counter
from dotenv import load_dotenv
from tabulate import tabulate
from ironforgedbot.database.database import db
from ironforgedbot.models.member import Member
from sqlalchemy import select

load_dotenv()

parser = argparse.ArgumentParser(description="Count messages after a given message ID")
parser.add_argument("--thread", type=int, required=True, help="Thread channel ID")
parser.add_argument(
    "--after", type=int, required=True, help="Count messages AFTER this ID"
)
args = parser.parse_args()

THREAD_ID = args.thread
AFTER_ID = args.after

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN environment variable must be set")


DISPLAY_TOTAL = 20

intents = discord.Intents.none()
intents.guilds = True
intents.messages = True
intents.members = True


class CounterClient(discord.Client):
    async def setup_hook(self):
        asyncio.create_task(self.run_counter())

    async def run_counter(self):
        await self.wait_until_ready()
        print(f"Logged in as {self.user}")

        thread = await self.fetch_channel(THREAD_ID)

        if not isinstance(thread, discord.Thread):
            print("Provided channel ID is not a thread.")
            await self.close()
            return

        counter = Counter()
        total = 0

        async for message in thread.history(
            limit=None, after=discord.Object(id=AFTER_ID), oldest_first=True
        ):
            if message.author.bot:
                continue

            counter[message.author.id] += 1
            total += 1

        print(f"\nProcessed {total} messages since {AFTER_ID}")
        await self.print_top(counter, thread.guild)

        await self.close()

    async def print_top(self, counter, guild):
        print("\nTop Counters\n")

        top_10 = counter.most_common(DISPLAY_TOTAL)
        discord_ids = [int(user_id) for user_id, _ in top_10]

        async with db.get_session() as session:
            stmt = select(Member).where(Member.discord_id.in_(discord_ids))
            result = await session.execute(stmt)
            members_list = list(result.scalars().all())
            # Ensure type consistency for dictionary keys
            members_by_id = {int(m.discord_id): m for m in members_list}

        table_data = []
        for rank, (user_id, count) in enumerate(top_10, 1):
            db_member = members_by_id.get(int(user_id))

            display_name = db_member.nickname if db_member else f"User {user_id}"
            rank_name = db_member.rank if db_member else "N/A"
            active = db_member.active if db_member else "False"

            table_data.append([rank, display_name, active, rank_name, count])

        print(
            tabulate(
                table_data,
                headers=["Rank", "Member", "IsActive", "Rank", "Contributions"],
                tablefmt="github",
            )
        )


async def main():
    client = CounterClient(intents=intents)
    async with client:
        await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
