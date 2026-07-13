import argparse
import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ironforgedcore.database import db  # noqa: E402

from api.consumer_service import (  # noqa: E402
    create_consumer,
    delete_consumer,
    get_consumer_by_name,
    grant_perm,
    list_consumers,
    revoke_perm,
    rotate_token,
    set_enabled,
    set_perms,
)
from api.permissions import KNOWN_PERMS  # noqa: E402
from scripts._api_console import Console, Prompter  # noqa: E402

_TOP_MENU = [
    "Create a new consumer",
    "Change a consumer's permissions (grant / revoke)",
    "Enable / disable a consumer",
    "Rotate a consumer's token",
    "Delete a consumer",
    "List consumers",
    "Exit",
]

_EXIT_INDEX = len(_TOP_MENU) - 1


def known_perm_options() -> list[tuple[str, str]]:
    return list(KNOWN_PERMS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage API consumers for IronForgedBot"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List all consumers")
    sub.add_parser(
        "interactive",
        help="Walk through consumer management with prompts",
    )
    return parser.parse_args(argv)


async def _cmd_list(session) -> int:
    consumers = await list_consumers(session)
    if not consumers:
        print("No consumers registered.")
        return 0
    print(f"{'NAME':<24} {'ENABLED':<8} {'PERMS':<60} ID")
    for c in consumers:
        print(f"{c.name:<24} {str(c.enabled):<8} " f"{','.join(c.perms):<60} {c.id}")
    return 0


async def _flow_create(prompter: Prompter, session) -> None:
    Console.section("Create new consumer")
    name = prompter.ask("Consumer name: ").strip()
    if not name:
        print("Name is required.")
        return

    existing = await get_consumer_by_name(session, name)
    if existing is not None:
        print(f"Consumer already exists: {name}")
        return

    description = (
        prompter.ask("Description (optional, Enter to skip): ").strip() or None
    )

    options = known_perm_options()
    selected: set[str] = set()
    if options:
        Console.info("Available permissions (toggle to add/remove):")
        selected = prompter.multi_select(options, current=[], prompt="toggle")

    print()
    Console.info("--- Summary ---")
    Console.info(f"  Name:        {name}")
    Console.info(f"  Description: {description or '(none)'}")
    Console.info(f"  Permissions: {', '.join(sorted(selected)) or '(none)'}")

    if not prompter.confirm("Create this consumer?"):
        print("Aborted.")
        return

    consumer, token = await create_consumer(
        session, name, perms=sorted(selected), description=description
    )
    print()
    print(f"Created consumer: {consumer.name} (id={consumer.id})")
    print(f"Token (save this, it will not be shown again): {token}")


async def _flow_change_perms(prompter: Prompter, session) -> None:
    consumers = await list_consumers(session)
    if not consumers:
        print("No consumers registered.")
        return

    Console.section("Change consumer permissions")
    for i, c in enumerate(consumers, start=1):
        perms_str = ",".join(c.perms) or "(none)"
        print(f"  {i}. {c.name:<24} perms: {perms_str}")

    idx = prompter.menu([c.name for c in consumers], prompt="Pick a consumer")
    consumer = consumers[idx]

    options = known_perm_options()
    if not options:
        print("No permissions registered.")
        return

    while True:
        Console.info(
            f"\nConsumer: {consumer.name}\n"
            f"Current perms: {', '.join(consumer.perms) or '(none)'}"
        )
        action = prompter.menu(
            ["Grant all missing", "Revoke all current", "Custom toggle"],
            prompt="Action",
        )
        all_perm_names = [name for name, _ in options]
        if action == 0:
            missing = [p for p in all_perm_names if p not in consumer.perms]
            new_perms = sorted(set(consumer.perms) | set(missing))
        elif action == 1:
            new_perms = []
        else:
            toggled = prompter.multi_select(
                options, current=consumer.perms, prompt="toggle"
            )
            new_perms = sorted(toggled)

        if new_perms == sorted(consumer.perms):
            print("No change.")
            return

        Console.info(f"  -> new perms: {', '.join(new_perms) or '(none)'}")
        if not prompter.confirm("Apply changes?"):
            print("Aborted.")
            return

        consumer = await set_perms(session, consumer.name, new_perms)
        added = sorted(set(new_perms) - set(consumer.perms))
        removed = sorted(set(consumer.perms) - set(new_perms))
        if added:
            print(f"  Added:   {', '.join(added)}")
        if removed:
            print(f"  Removed: {', '.join(removed)}")
        return


async def _flow_toggle_enabled(prompter: Prompter, session) -> None:
    consumers = await list_consumers(session)
    if not consumers:
        print("No consumers registered.")
        return

    Console.section("Enable / disable consumer")
    for i, c in enumerate(consumers, start=1):
        state = "enabled " if c.enabled else "disabled"
        print(f"  {i}. {c.name:<24} ({state})")

    idx = prompter.menu([c.name for c in consumers], prompt="Pick a consumer")
    consumer = consumers[idx]
    new_state = not consumer.enabled
    verb = "Enable" if new_state else "Disable"
    if not prompter.confirm(f"{verb} {consumer.name}?"):
        print("Aborted.")
        return
    consumer = await set_enabled(session, consumer.name, new_state)
    print(f"{verb}d {consumer.name}")


async def _flow_rotate_token(prompter: Prompter, session) -> None:
    consumers = await list_consumers(session)
    if not consumers:
        print("No consumers registered.")
        return

    Console.section("Rotate consumer token")
    for i, c in enumerate(consumers, start=1):
        print(f"  {i}. {c.name}")
    idx = prompter.menu([c.name for c in consumers], prompt="Pick a consumer")
    consumer = consumers[idx]

    Console.info("\nRotating the token immediately invalidates the old token.")
    if not prompter.confirm(f"Rotate token for {consumer.name}?"):
        print("Aborted.")
        return

    consumer, token = await rotate_token(session, consumer.name)
    print(f"Rotated token for {consumer.name}")
    print(f"New token (save this): {token}")


async def _flow_delete(prompter: Prompter, session) -> None:
    consumers = await list_consumers(session)
    if not consumers:
        print("No consumers registered.")
        return

    Console.section("Delete consumer")
    for i, c in enumerate(consumers, start=1):
        print(f"  {i}. {c.name}")
    idx = prompter.menu([c.name for c in consumers], prompt="Pick a consumer")
    consumer = consumers[idx]

    Console.info(f"\nThis permanently deletes the consumer and revokes their token.")
    confirm_name = prompter.ask(
        f"Type the consumer name ({consumer.name}) to confirm: "
    ).strip()
    if confirm_name != consumer.name:
        print("Name did not match. Aborted.")
        return

    await delete_consumer(session, consumer.name)
    print(f"Deleted consumer: {consumer.name}")


async def _flow_list(prompter: Prompter, session) -> None:
    Console.section("Consumers")
    await _cmd_list(session)
    prompter.ask("\nPress Enter to return to menu...")


async def _interactive_loop(prompter: Prompter) -> None:
    async with db.get_session() as session:
        while True:
            Console.header("API Consumer Management")
            choice = prompter.menu(_TOP_MENU, prompt="What would you like to do")
            if choice == _EXIT_INDEX:
                print("Bye.")
                return
            try:
                if choice == 0:
                    await _flow_create(prompter, session)
                elif choice == 1:
                    await _flow_change_perms(prompter, session)
                elif choice == 2:
                    await _flow_toggle_enabled(prompter, session)
                elif choice == 3:
                    await _flow_rotate_token(prompter, session)
                elif choice == 4:
                    await _flow_delete(prompter, session)
                elif choice == 5:
                    await _flow_list(prompter, session)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
            prompter.ask("\nPress Enter to return to menu...")


async def run(args: argparse.Namespace, prompter: Prompter | None = None) -> int:
    prompter = prompter or Prompter()
    if args.command == "list":
        async with db.get_session() as session:
            return await _cmd_list(session)
    if args.command == "interactive":
        await _interactive_loop(prompter)
        return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    async def _runner() -> int:
        try:
            return await run(args)
        finally:
            if db is not None and db._engine is not None:
                await db.dispose()

    return asyncio.run(_runner())


if __name__ == "__main__":
    sys.exit(main())
