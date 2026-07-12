import argparse
import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ironforgedbot.database.database import db  # noqa: E402

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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage API consumers for IronForgedBot"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Create a new consumer")
    add_p.add_argument("--name", required=True)
    add_p.add_argument("--perms", default="", help="Comma-separated perm list")
    add_p.add_argument("--description", default=None)

    sub.add_parser("list", help="List all consumers")

    grant_p = sub.add_parser("grant", help="Grant a permission")
    grant_p.add_argument("--name", required=True)
    grant_p.add_argument("--perm", required=True)

    revoke_p = sub.add_parser("revoke", help="Revoke a permission")
    revoke_p.add_argument("--name", required=True)
    revoke_p.add_argument("--perm", required=True)

    set_p = sub.add_parser("set-perms", help="Replace consumer's perm list")
    set_p.add_argument("--name", required=True)
    set_p.add_argument("--perms", required=True, help="Comma-separated perm list")

    enable_p = sub.add_parser("enable", help="Enable a consumer")
    enable_p.add_argument("--name", required=True)

    disable_p = sub.add_parser("disable", help="Disable a consumer")
    disable_p.add_argument("--name", required=True)

    rotate_p = sub.add_parser("rotate", help="Rotate a consumer's token")
    rotate_p.add_argument("--name", required=True)

    delete_p = sub.add_parser("delete", help="Delete a consumer")
    delete_p.add_argument("--name", required=True)

    return parser.parse_args(argv)


def _parse_perms(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


async def run(args: argparse.Namespace) -> int:
    try:
        async with db.get_session() as session:
            if args.command == "add":
                perms = _parse_perms(args.perms)
                consumer, token = await create_consumer(
                    session, args.name, perms=perms, description=args.description
                )
                print(f"Created consumer: {consumer.name} (id={consumer.id})")
                print(f"Token (save this, it will not be shown again): {token}")
                return 0

            if args.command == "list":
                consumers = await list_consumers(session)
                if not consumers:
                    print("No consumers registered.")
                    return 0
                print(f"{'NAME':<24} {'ENABLED':<8} {'PERMS':<60} ID")
                for c in consumers:
                    print(
                        f"{c.name:<24} {str(c.enabled):<8} "
                        f"{','.join(c.perms):<60} {c.id}"
                    )
                return 0

            if args.command == "grant":
                consumer = await grant_perm(session, args.name, args.perm)
                print(f"Granted {args.perm} to {consumer.name}")
                return 0

            if args.command == "revoke":
                consumer = await revoke_perm(session, args.name, args.perm)
                print(f"Revoked {args.perm} from {consumer.name}")
                return 0

            if args.command == "set-perms":
                perms = _parse_perms(args.perms)
                consumer = await set_perms(session, args.name, perms)
                print(f"Set perms for {consumer.name}: {','.join(consumer.perms)}")
                return 0

            if args.command == "enable":
                consumer = await set_enabled(session, args.name, True)
                print(f"Enabled {consumer.name}")
                return 0

            if args.command == "disable":
                consumer = await set_enabled(session, args.name, False)
                print(f"Disabled {consumer.name}")
                return 0

            if args.command == "rotate":
                consumer, token = await rotate_token(session, args.name)
                print(f"Rotated token for {consumer.name}")
                print(f"New token (save this): {token}")
                return 0

            if args.command == "delete":
                if not await get_consumer_by_name(session, args.name):
                    print(f"Consumer not found: {args.name}", file=sys.stderr)
                    return 1
                await delete_consumer(session, args.name)
                print(f"Deleted consumer: {args.name}")
                return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 2

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
