from collections import Counter
import random

from ironforgedbot.commands.holiday.trick_or_treat_handler import TrickOrTreat


attempts = 10_000
weights = [1 / item.value for item in TrickOrTreat]
counter = Counter()

for _ in range(attempts):
    selected = random.choices(list(TrickOrTreat), weights=weights)[0]
    counter[selected.name] += 1

print(f"Distribution of selections after {attempts:,} attempts:\n")
sorted = counter.most_common()
for thing, count in sorted:
    print(f"{thing}: {count:,} times ({(count / attempts) * 100:.2f}%)")
