"""Stdlib-only console + prompter helpers for interactive API management scripts.

No external dependencies. The Prompter class is the single chokepoint for user
input, so tests can replace it with a fake that returns canned answers.
"""

from __future__ import annotations

from typing import Iterable, Sequence


class Console:
    """Plain text output helpers. No colors (works in any terminal / log)."""

    WIDTH = 60

    @staticmethod
    def header(title: str) -> None:
        bar = "=" * Console.WIDTH
        print()
        print(bar)
        print(f"  {title}")
        print(bar)

    @staticmethod
    def section(title: str) -> None:
        print()
        print(f"--- {title} ---")

    @staticmethod
    def info(text: str) -> None:
        print(text)

    @staticmethod
    def blank() -> None:
        print()


class Prompter:
    """Single chokepoint for user input. Replace with a fake in tests."""

    def ask(self, text: str) -> str:
        return input(text)

    def confirm(self, text: str, default: bool = False) -> bool:
        suffix = " [Y/n]" if default else " [y/N]"
        while True:
            answer = input(f"{text}{suffix}: ").strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            print("Please answer y or n.")

    def menu(self, options: Sequence[str], prompt: str = "Select") -> int:
        """Show numbered options, re-prompt on invalid input. Returns 0-indexed."""
        while True:
            for i, opt in enumerate(options, start=1):
                print(f"  {i}. {opt}")
            raw = input(f"{prompt} [1-{len(options)}]: ").strip()
            try:
                idx = int(raw)
            except ValueError:
                print(f"Please enter a number between 1 and {len(options)}.")
                continue
            if 1 <= idx <= len(options):
                return idx - 1
            print(f"Please enter a number between 1 and {len(options)}.")

    def multi_select(
        self,
        options: Sequence[tuple[str, str]],
        current: Iterable[str],
        prompt: str = "Select",
    ) -> set[str]:
        """Toggle-style multi-select. Returns the resulting set.

        `options` is a sequence of (key, label) tuples shown as a numbered list
        with [x]/[ ] markers for the current selection. The user types
        comma-separated numbers to toggle. Empty input leaves selection
        unchanged. The result is shown before returning so the user can confirm.
        """
        current_set = set(current)
        while True:
            print(f"  ({prompt}: comma-separated numbers, Enter to keep current)")
            for i, (key, label) in enumerate(options, start=1):
                marker = "[x]" if key in current_set else "[ ]"
                print(f"  {marker} {i}. {key:<32} {label}")
            raw = input(f"Toggle [1-{len(options)}, or Enter]: ").strip()
            if not raw:
                return current_set
            try:
                indices = [int(x) for x in raw.split(",") if x.strip()]
            except ValueError:
                print("Please enter comma-separated numbers.")
                continue
            if not all(1 <= i <= len(options) for i in indices):
                print(f"Please enter numbers between 1 and {len(options)}.")
                continue
            for i in indices:
                key = options[i - 1][0]
                if key in current_set:
                    current_set.discard(key)
                else:
                    current_set.add(key)
            print(f"  -> current: {', '.join(sorted(current_set)) or '(none)'}")
            return current_set
