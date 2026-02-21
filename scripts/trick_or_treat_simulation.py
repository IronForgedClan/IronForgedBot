import os
import sys

# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from collections import Counter
import random

from tabulate import tabulate

from ironforgedbot.commands.trickortreat.trick_or_treat_constants import TrickOrTreat

attempts = 30_000
outcomes = list(TrickOrTreat)
weights = [item.value for item in outcomes]
total_weight = sum(weights)
counter = Counter()

for _ in range(attempts):
    selected = random.choices(outcomes, weights=weights)[0]
    counter[selected.name] += 1

print(f"Distribution of outcomes after {attempts:,} attempts:")
print(f"Total weight: {total_weight}\n")

table_data = [
    [
        outcome.name,
        f"{counter[outcome.name]:,}",
        f"{(counter[outcome.name] / attempts) * 100:.2f}%",
        f"{(outcome.value / total_weight) * 100:.2f}%",
    ]
    for outcome in outcomes
]

table_data.sort(key=lambda x: int(x[1].replace(",", "")), reverse=True)

print(
    tabulate(
        table_data,
        headers=["Outcome", "Count", "Actual %", "Expected %"],
        colalign=("left", "right", "right", "right"),
        tablefmt="github",
    )
)
