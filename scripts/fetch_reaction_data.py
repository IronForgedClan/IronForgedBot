#!/usr/bin/env python3
import os
import sys

# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import discord
import asyncio
import argparse
from dotenv import load_dotenv
from ironforgedbot.common.helpers import normalize_discord_string

load_dotenv()

parser = argparse.ArgumentParser(
    description="Fetch Discord member display names who reacted to a message with a specific emoji"
)
parser.add_argument(
    "--channel", type=int, required=True, help="Channel ID where the message is located"
)
parser.add_argument(
    "--message", type=int, required=True, help="Message ID to fetch reactions from"
)
parser.add_argument(
    "--emoji", type=str, required=True, help="Custom emoji name or ID to filter by"
)
parser.add_argument("--output", type=str, help="Output file path (defaults to stdout)")
args = parser.parse_args()

CHANNEL_ID = args.channel
MESSAGE_ID = args.message
EMOJI_FILTER = args.emoji
OUTPUT_FILE = args.output

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("Error: BOT_TOKEN environment variable must be set", file=sys.stderr)
    sys.exit(1)

intents = discord.Intents.none()
intents.guilds = True
intents.messages = True
intents.members = True
intents.reactions = True


class ReactionClient(discord.Client):
    async def setup_hook(self):
        asyncio.create_task(self.fetch_reactions())

    async def fetch_reactions(self):
        await self.wait_until_ready()
        print(f"Logged in as {self.user}", file=sys.stderr)

        try:
            channel = await self.fetch_channel(CHANNEL_ID)
        except discord.NotFound:
            print(f"Error: Channel {CHANNEL_ID} not found", file=sys.stderr)
            await self.close()
            return
        except discord.Forbidden:
            print(
                f"Error: No permission to access channel {CHANNEL_ID}", file=sys.stderr
            )
            await self.close()
            return

        try:
            message = await channel.fetch_message(MESSAGE_ID)
        except discord.NotFound:
            print(
                f"Error: Message {MESSAGE_ID} not found in channel {CHANNEL_ID}",
                file=sys.stderr,
            )
            await self.close()
            return
        except discord.Forbidden:
            print(
                f"Error: No permission to access message {MESSAGE_ID}", file=sys.stderr
            )
            await self.close()
            return

        matching_reaction = None
        for reaction in message.reactions:
            emoji = reaction.emoji
            if isinstance(emoji, discord.PartialEmoji) or isinstance(
                emoji, discord.Emoji
            ):
                if emoji.name == EMOJI_FILTER or str(emoji.id) == EMOJI_FILTER:
                    matching_reaction = reaction
                    break
            else:
                if str(emoji) == EMOJI_FILTER:
                    matching_reaction = reaction
                    break

        if not matching_reaction:
            print(
                f"Error: Emoji '{EMOJI_FILTER}' not found on message", file=sys.stderr
            )
            if message.reactions:
                print("Available reactions on this message:", file=sys.stderr)
                for reaction in message.reactions:
                    emoji = reaction.emoji
                    if isinstance(emoji, discord.PartialEmoji) or isinstance(
                        emoji, discord.Emoji
                    ):
                        print(f"  - {emoji.name} (ID: {emoji.id})", file=sys.stderr)
                    else:
                        print(f"  - {emoji}", file=sys.stderr)
            else:
                print("This message has no reactions.", file=sys.stderr)
            await self.close()
            return

        display_names = []
        guild = message.guild

        async for user in matching_reaction.users():
            if user.bot:
                continue

            if guild:
                member = guild.get_member(user.id)
                if not member:
                    try:
                        member = await guild.fetch_member(user.id)
                    except discord.NotFound:
                        member = None

                if member:
                    display_names.append(normalize_discord_string(member.display_name))
                else:
                    display_names.append(normalize_discord_string(user.display_name))
            else:
                display_names.append(normalize_discord_string(user.display_name))

        output_line = ",".join(display_names)
        if OUTPUT_FILE:
            with open(OUTPUT_FILE, "w") as f:
                f.write(output_line + "\n")
        else:
            print(output_line)

        print(f"Found {len(display_names)} reactions", file=sys.stderr)
        await self.close()


async def main():
    client = ReactionClient(intents=intents)
    async with client:
        await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
