import os
import sys

# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import re

from ironforgedbot.storage.sheets import STORAGE


async def get_results():
    total_gained = 0
    total_lost = 0
    players = {}
    pattern = r"Ingots:\s*(\d+)"

    print("loading data...")
    changelog = await STORAGE.read_changelog()

    print("processing values...")
    for entry in changelog:
        if len(entry) == 6 and entry[5] == "[BOT] Trick or Treat":
            player = entry[0]
            prev_match = re.search(pattern, entry[2])
            new_match = re.search(pattern, entry[3])

            if prev_match and new_match:
                if player not in players:
                    players[player] = {"gained": 0, "lost": 0}

                previous_ingots = int(prev_match.group(1))
                new_ingots = int(new_match.group(1))

                if new_ingots < previous_ingots:
                    diff = previous_ingots - new_ingots
                    players[player]["lost"] += diff
                    total_lost += diff
                else:
                    diff = new_ingots - previous_ingots
                    players[player]["gained"] += diff
                    total_gained += diff

    print("building output...")
    sorted_gained = sorted(players.items(), key=lambda x: x[1]["gained"], reverse=True)
    sorted_lost = sorted(players.items(), key=lambda x: x[1]["lost"], reverse=True)

    print("\nTOP GAINS:")
    for player, stats in sorted_gained[:10]:
        print(f"{player} (+{stats['gained']:,})")

    print("\nTOP LOSSES:")
    for player, stats in sorted_lost[:10]:
        print(f"{player} (-{stats['lost']:,})")

    net_changes = {
        player: stats["gained"] - stats["lost"] for player, stats in players.items()
    }
    sorted_by_net_change = sorted(net_changes.items(), key=lambda x: x[1], reverse=True)

    print("\nNET WINNERS:")
    for player, net in sorted_by_net_change[:10]:
        print(f"{player} (+{net:,})")

    print("\nNET LOSERS:")
    for player, net in sorted_by_net_change[-10:][::-1]:
        print(f"{player} ({net:,})")

    print(f"\nTotal Lost:   {total_lost:,}\nTotal Gained: {total_gained:,}")


if __name__ == "__main__":
    asyncio.run(get_results())
