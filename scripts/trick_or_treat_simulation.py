import os
import sys

# Add the parent directory to sys.path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from collections import Counter
import random

from tabulate import tabulate

from ironforgedbot.commands.holiday.trick_or_treat_constants import TrickOrTreat


attempts = 20_000
outcomes = list(TrickOrTreat)
weights = [item.value for item in outcomes]
total_weight = sum(weights)
counter = Counter()

for _ in range(attempts):
    selected = random.choices(outcomes, weights=weights)[0]
    counter[selected.name] += 1

print(f"Distribution of outcomes after {attempts:,} attempts:")
print(f"Total weight: {total_weight}\n")

# Sort by count (highest to lowest)
sorted_results = sorted(counter.items(), key=lambda x: x[1], reverse=True)

table_data = [
    [
        name,
        f"{count:,}",
        f"{(count / attempts) * 100:.2f}%",
        f"{(TrickOrTreat[name].value / total_weight) * 100:.2f}%",
    ]
    for name, count in sorted_results
]

print(
    tabulate(
        table_data,
        headers=["Outcome", "Count", "Actual %", "Expected %"],
        colalign=("left", "right", "right", "right"),
        tablefmt="github",
    )
)
