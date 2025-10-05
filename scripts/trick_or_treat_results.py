"""
Trick or Treat Results Analysis Script

This script analyzes trick-or-treat event results from the database changelog.

Usage:
    Run this script inside the Docker container to access the database:

    docker compose run --rm bot python scripts/trick_or_treat_results.py
"""

import os
import sys

# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from datetime import datetime, timezone
from collections import defaultdict

from dotenv import load_dotenv
from sqlalchemy import select, and_, extract
from tabulate import tabulate

from ironforgedbot.database.database import db
from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.models.member import Member

# Load environment variables from .env file in project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path)


async def get_results():
    """Analyze trick-or-treat results from the changelog."""
    current_year = datetime.now(timezone.utc).year

    total_gained = 0
    total_lost = 0
    players = {}
    outcome_types = defaultdict(int)
    steal_stats = defaultdict(int)  # Track ingots stolen by each player
    victim_stats = defaultdict(int)  # Track ingots stolen from each player

    print(f"Loading trick-or-treat data for {current_year}...\n")

    async with db.get_session() as session:
        # Query changelog entries for trick-or-treat events in current year
        stmt = (
            select(Changelog, Member.nickname)
            .join(Member, Changelog.member_id == Member.id)
            .where(
                and_(
                    Changelog.comment.like("Trick or treat:%"),
                    extract("year", Changelog.timestamp) == current_year,
                )
            )
            .order_by(Changelog.timestamp)
        )

        result = await session.execute(stmt)
        entries = result.all()

        print(f"Processing {len(entries)} changelog entries...\n")

        for changelog, nickname in entries:
            outcome_type = changelog.comment.replace("Trick or treat: ", "")
            outcome_types[outcome_type] += 1

            if outcome_type == "steal success":
                previous = int(changelog.previous_value)
                new = int(changelog.new_value)
                stolen_amount = new - previous
                steal_stats[nickname] += stolen_amount
            elif outcome_type.startswith("stolen by "):
                previous = int(changelog.previous_value)
                new = int(changelog.new_value)
                stolen_amount = previous - new  # Victim lost ingots
                victim_stats[nickname] += stolen_amount

            # Initialize player if not seen before
            if nickname not in players:
                players[nickname] = {"gained": 0, "lost": 0}

            # Calculate difference
            previous = int(changelog.previous_value)
            new = int(changelog.new_value)
            diff = new - previous

            if diff < 0:
                # Player lost ingots
                loss_amount = abs(diff)
                players[nickname]["lost"] += loss_amount
                total_lost += loss_amount
            else:
                # Player gained ingots
                players[nickname]["gained"] += diff
                total_gained += diff

    print("=" * 50)
    print(f"TRICK OR TREAT RESULTS - {current_year}")
    print("=" * 50)
    print()

    print("OUTCOME TYPE BREAKDOWN:")
    outcome_table = [
        [outcome, f"{count:,}"] for outcome, count in sorted(outcome_types.items())
    ]
    print(tabulate(outcome_table, headers=["Outcome Type", "Count"], tablefmt="github"))
    print()

    # Top gains
    sorted_gained = sorted(players.items(), key=lambda x: x[1]["gained"], reverse=True)
    print("TOP 10 GAINS:")
    gains_table = [
        [player, f"+{stats['gained']:,}"] for player, stats in sorted_gained[:10]
    ]
    print(
        tabulate(
            gains_table,
            headers=["Player", "Ingots Gained"],
            colalign=("left", "right"),
            tablefmt="github",
        )
    )
    print()

    sorted_lost = sorted(players.items(), key=lambda x: x[1]["lost"], reverse=True)
    print("TOP 10 LOSSES:")
    losses_table = [
        [player, f"-{stats['lost']:,}"] for player, stats in sorted_lost[:10]
    ]
    print(
        tabulate(
            losses_table,
            headers=["Player", "Ingots Lost"],
            colalign=("left", "right"),
            tablefmt="github",
        )
    )
    print()

    if steal_stats:
        sorted_thieves = sorted(steal_stats.items(), key=lambda x: x[1], reverse=True)
        print("TOP 10 BIGGEST THIEVES:")
        thieves_table = [
            [player, f"+{stolen:,}"] for player, stolen in sorted_thieves[:10]
        ]
        print(
            tabulate(
                thieves_table,
                headers=["Player", "Ingots Stolen"],
                colalign=("left", "right"),
                tablefmt="github",
            )
        )
        print()

    if victim_stats:
        sorted_victims = sorted(victim_stats.items(), key=lambda x: x[1], reverse=True)
        print("TOP 10 BIGGEST VICTIMS:")
        victims_table = [
            [player, f"-{stolen:,}"] for player, stolen in sorted_victims[:10]
        ]
        print(
            tabulate(
                victims_table,
                headers=["Player", "Ingots Stolen From"],
                colalign=("left", "right"),
                tablefmt="github",
            )
        )
        print()

    net_changes = {
        player: stats["gained"] - stats["lost"] for player, stats in players.items()
    }
    sorted_by_net = sorted(net_changes.items(), key=lambda x: x[1], reverse=True)

    print("TOP 10 NET WINNERS:")
    net_winners_table = [
        [player, f"+{net:,}" if net >= 0 else f"{net:,}"]
        for player, net in sorted_by_net[:10]
    ]
    print(
        tabulate(
            net_winners_table,
            headers=["Player", "Net Change"],
            colalign=("left", "right"),
            tablefmt="github",
        )
    )
    print()

    print("TOP 10 NET LOSERS:")
    net_losers_table = [
        [player, f"{net:,}"] for player, net in sorted_by_net[-10:][::-1]
    ]
    print(
        tabulate(
            net_losers_table,
            headers=["Player", "Net Change"],
            colalign=("left", "right"),
            tablefmt="github",
        )
    )
    print()

    print("=" * 50)
    summary_table = [
        ["Total Ingots Lost", f"{total_lost:,}"],
        ["Total Ingots Gained", f"{total_gained:,}"],
        ["Net Change", f"{total_gained - total_lost:,}"],
        ["Total Players", f"{len(players):,}"],
    ]
    print(
        tabulate(
            summary_table,
            headers=["Metric", "Value"],
            tablefmt="github",
            colalign=("left", "right"),
        )
    )
    print("=" * 50)


async def main():
    """Main entry point that properly cleans up database connections."""
    try:
        await get_results()
    finally:
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
