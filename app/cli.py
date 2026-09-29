"""Administrative commands.

    python -m app.cli create-admin <login>     # first admin account (asks for a password)
    python -m app.cli create-admin <login> --temporary   # prints a one-time password instead
    python -m app.cli reset-password <login>   # prints a new temporary password
    python -m app.cli import-groups            # adds the groups from the EduPage timetable
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from app.config import get_settings
from app.db import create_engine, create_session_factory, init_db, repo
from app.db.models import StaffRole
from app.services import edupage
from app.services.passwords import normalize_username, password_problem


async def create_admin(login: str, name: str | None, temporary: bool = False) -> None:
    username = normalize_username(login)
    if username is None:
        sys.exit("Invalid login: use 3-32 characters a-z, 0-9, '.', '-', '_'")
    password = None
    if not temporary:
        password = getpass.getpass("Password: ")
        if problem := password_problem(password):
            sys.exit(f"Password rejected: {problem} (at least 8 characters, letters and digits)")
        if getpass.getpass("Repeat password: ") != password:
            sys.exit("Passwords don't match")
    engine = create_engine(get_settings().database_url)
    await init_db(engine)
    async with create_session_factory(engine)() as s:
        if await repo.get_account_by_username(s, username):
            sys.exit(f"Account {username!r} already exists")
        _, temp = await repo.create_account(s, username=username, display_name=name, roles=[(StaffRole.ADMIN, None)], password=password)
        await repo.audit(s, "cli", "account.create", entity="account", summary=f"{username} · admin")
        await s.commit()
    await engine.dispose()
    print(f"Admin account {username!r} created. Sign in on the website, and send /login to the bot.")
    if temporary:
        print(f"Temporary password: {temp}\nIt must be changed at the first sign-in.")


async def reset_password(login: str) -> None:
    engine = create_engine(get_settings().database_url)
    await init_db(engine)
    async with create_session_factory(engine)() as s:
        account = await repo.get_account_by_username(s, login)
        if account is None:
            sys.exit(f"No account {login!r}")
        password = await repo.reset_password(s, account)
        await repo.audit(s, "cli", "account.reset_password", entity="account", entity_id=account.id, summary=account.username)
        await s.commit()
    await engine.dispose()
    print(f"Temporary password for {login!r}: {password}\nIt must be changed at the next sign-in.")


async def import_groups() -> None:
    settings = get_settings()
    if not settings.edupage_url:
        sys.exit("EDUPAGE_URL is empty")
    try:
        names = await edupage.fetch_group_names(settings.edupage_url)
    except edupage.EdupageError as e:
        sys.exit(f"Couldn't read EduPage: {e}")
    engine = create_engine(settings.database_url)
    await init_db(engine)
    async with create_session_factory(engine)() as s:
        result = await repo.import_groups(s, names)
        await repo.audit(
            s, "cli", "group.import", entity="group",
            summary=f"EduPage: +{len(result.added)}", details={"added": ", ".join(result.added)} if result.added else None,
        )
        await s.commit()
    await engine.dispose()
    print(f"EduPage lists {len(names)} groups. Added {len(result.added)}: {', '.join(result.added) or '-'}")
    print(f"Already here: {len(result.existing)}")
    if result.missing:
        print(f"Here but not on EduPage (kept): {', '.join(result.missing)}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-admin", help="create an admin account")
    p.add_argument("login")
    p.add_argument("--name", help="display name")
    p.add_argument("--temporary", action="store_true", help="generate a one-time password (changed at first sign-in)")
    p = sub.add_parser("reset-password", help="set a new temporary password")
    p.add_argument("login")
    sub.add_parser("import-groups", help="add the groups from the EduPage timetable")
    args = parser.parse_args()
    if args.cmd == "create-admin":
        asyncio.run(create_admin(args.login, args.name, args.temporary))
    elif args.cmd == "import-groups":
        asyncio.run(import_groups())
    else:
        asyncio.run(reset_password(args.login))


if __name__ == "__main__":
    main()
