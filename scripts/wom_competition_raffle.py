import os
import sys

# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
import asyncio
import random

from dotenv import load_dotenv
from tabulate import tabulate

from ironforgedbot.services.wom_service import WomService, WomServiceError

# Load environment variables from .env file in project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path)


async def run_raffle(competition_id: int, xp_per_ticket: int):
    """This script loads participants from a Wise Old Man competition, awards tickets
    based on XP gained and runs a raffle to select a winner.

    Args:
        competition_id: WOM competition ID
        xp_per_ticket: XP required to earn one ticket
    """
    print(f"Loading competition data for competition ID: {competition_id}")
    print(f"XP per ticket: {xp_per_ticket:,}\n")

    async with WomService() as wom_service:
        try:
            client = await wom_service._get_client()

            result = await client.competitions.get_details(competition_id)

            if result.is_err:
                error_details = result.unwrap_err()
                print(f"Error fetching competition: {error_details}")
                return

            competition = result.unwrap()

            print(f"Competition: {competition.title}")
            print(f"Metric: {competition.metric.name}")
            print(f"Type: {competition.type.name}")
            print(f"Participants: {len(competition.participations)}\n")

            participants = {}
            all_tickets = []

            for participation in competition.participations:
                player_name = participation.player.display_name
                gained_xp = participation.progress.gained
                tickets = gained_xp // xp_per_ticket if gained_xp > 0 else 0

                if player_name not in participants:
                    participants[player_name] = {
                        "player": player_name,
                        "xp": 0,
                        "tickets": 0,
                    }

                participants[player_name]["xp"] += gained_xp
                participants[player_name]["tickets"] += tickets

                all_tickets.extend([player_name] * tickets)

            participants_sorted = sorted(
                participants.values(),
                key=lambda x: (x["tickets"], x["xp"]),
                reverse=True,
            )

            table_data = [
                [i + 1, p["player"], f"{p['xp']:,}", p["tickets"]]
                for i, p in enumerate(participants_sorted)
            ]

            print(
                tabulate(
                    table_data,
                    headers=["Rank", "Player", "XP Gained", "Tickets"],
                    tablefmt="github",
                    colalign=("right", "left", "right", "right"),
                )
            )
            print()

            total_tickets = len(all_tickets)
            participants_with_tickets = sum(
                1 for p in participants_sorted if p["tickets"] > 0
            )

            summary_table = [
                ["Total Participants", f"{len(participants):,}"],
                ["Participants with Tickets", f"{participants_with_tickets:,}"],
                ["Total Tickets", f"{total_tickets:,}"],
            ]
            print(
                tabulate(
                    summary_table,
                    headers=["Metric", "Value"],
                    tablefmt="github",
                    colalign=("left", "right"),
                )
            )

            if total_tickets == 0:
                print("No tickets, no winner!")
                return

            winner = random.choice(all_tickets)
            winner_data = participants[winner]

            win_probability = (winner_data["tickets"] / total_tickets) * 100

            print("\n\n===== RAFFLE WINNER =====\n")

            winner_table = [
                ["Player", winner],
                ["XP Gained", f"{winner_data['xp']:,}"],
                ["Tickets", f"{winner_data['tickets']:,}"],
                ["Win Probability", f"{win_probability:.2f}%"],
            ]

            print(
                tabulate(
                    winner_table,
                    tablefmt="github",
                    colalign=("left", "right"),
                )
            )

        except WomServiceError as e:
            print(f"WOM Service Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Run a raffle based on WOM competition XP gains"
    )
    parser.add_argument(
        "competition_id", type=int, help="WOM competition ID to load participants from"
    )
    parser.add_argument(
        "xp_per_ticket",
        type=int,
        help="XP required to earn one raffle ticket",
    )

    args = parser.parse_args()

    if args.xp_per_ticket <= 0:
        print("Error: xp_per_ticket must be greater than 0")
        sys.exit(1)

    asyncio.run(run_raffle(args.competition_id, args.xp_per_ticket))


if __name__ == "__main__":
    main()
