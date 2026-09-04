"""Create, promote, or rotate an admin account.

Self-registration through the API is hard-wired to "buyer", so the first
admin has to be made here. Re-running for an existing email synchronizes the
name, role, and password so stale admin credentials can be repaired safely.

Run from the backend directory:

    cd backend
    python scripts/create_admin.py --email admin@area303.dev --password '<strong-secret>'

Credentials can also come from ADMIN_EMAIL / ADMIN_PASSWORD env vars.
Requires the database to be migrated first (`alembic upgrade head`).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Python puts the *script's* directory on sys.path, not the working directory, so
# `python scripts/create_admin.py` from backend/ cannot see `app` without this.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import user_service  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote an admin user.")
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"))
    parser.add_argument("--name", default=os.getenv("ADMIN_NAME", "Quan tri vien"))
    args = parser.parse_args()

    if not args.email or not args.password:
        parser.error(
            "--email and --password are required "
            "(or set ADMIN_EMAIL / ADMIN_PASSWORD)."
        )
    if len(args.password) < 8:
        parser.error("Password must be at least 8 characters.")

    async with SessionLocal() as db:
        existing = await user_service.get_by_email(db, args.email)
        if existing is not None:
            existing.role = "admin"
            existing.name = args.name
            existing.password_hash = hash_password(args.password)
            await db.commit()
            print(f"updated admin credentials: {existing.email} (id={existing.id})")
            return 0

        user = await user_service.create_user(
            db,
            email=args.email,
            password=args.password,
            name=args.name,
            role="admin",
        )
        print(f"created admin: {user.email} (id={user.id})")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
