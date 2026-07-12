import argparse
import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import ApiConsumer, ApiPermission

try:
    from ironforgedbot.database.database import db
except RuntimeError:
    db = None


async def list_perms(session: AsyncSession) -> list[ApiPermission]:
    result = await session.execute(select(ApiPermission).order_by(ApiPermission.name))
    return list(result.scalars().all())


async def add_perm(
    session: AsyncSession, name: str, description: str | None = None
) -> ApiPermission:
    existing = await session.execute(
        select(ApiPermission).where(ApiPermission.name == name)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Permission already exists: {name}")
    perm = ApiPermission(
        name=name, description=description, created_at=datetime.now(tz=timezone.utc)
    )
    session.add(perm)
    await session.commit()
    await session.refresh(perm)
    return perm


async def remove_perm(session: AsyncSession, name: str) -> bool:
    perm = await session.execute(
        select(ApiPermission).where(ApiPermission.name == name)
    )
    perm_obj = perm.scalar_one_or_none()
    if perm_obj is None:
        return False

    consumers = await session.execute(select(ApiConsumer))
    for consumer in consumers.scalars().all():
        if name in (consumer.perms or []):
            raise ValueError(
                f"Cannot remove perm {name!r}: in use by consumer {consumer.name!r}"
            )

    await session.delete(perm_obj)
    await session.commit()
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage API permissions")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all known permissions")

    add_p = sub.add_parser("add", help="Add a permission")
    add_p.add_argument("--name", required=True)
    add_p.add_argument("--description", default=None)

    remove_p = sub.add_parser("remove", help="Remove a permission")
    remove_p.add_argument("--name", required=True)

    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    if db is None:
        print("Database not configured (DATABASE_URL missing)", file=sys.stderr)
        return 2

    try:
        async with db.get_session() as session:
            if args.command == "list":
                perms = await list_perms(session)
                if not perms:
                    print("No permissions registered.")
                    return 0
                for p in perms:
                    print(f"{p.name:<40} {p.description or ''}")
                return 0

            if args.command == "add":
                perm = await add_perm(session, args.name, args.description)
                print(f"Added permission: {perm.name}")
                return 0

            if args.command == "remove":
                if not await remove_perm(session, args.name):
                    print(f"Permission not found: {args.name}", file=sys.stderr)
                    return 1
                print(f"Removed permission: {args.name}")
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
