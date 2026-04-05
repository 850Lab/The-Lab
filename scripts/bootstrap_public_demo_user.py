#!/usr/bin/env python3
"""
Grant letter + mailing credits to the dedicated public-demo user (``users.id``).

To **create** the reserved synthetic demo row first, run:

  python scripts/ensure_public_demo_test_account.py

The interactive ``/demo`` run normally waives payment for visitors, but letter generation
still needs a healthy entitlement balance on the underlying demo user if waiver or admin
paths fail. Use this script to top up credits for a pinned id or your auto-created row.

Usage (repo root; ``DATABASE_URL`` in ``.env`` or environment):

  python scripts/bootstrap_public_demo_user.py 123

Optional env (only if you pin the demo to a specific row instead of the auto-created system user):

  PUBLIC_DEMO_USER_ID=123
  PUBLIC_DEMO_ENABLED=1   # production-like deploys only

Optional: ``PUBLIC_DEMO_SECRET`` + matching ``VITE_PUBLIC_DEMO_SECRET`` in ``web/.env.local``
before ``npm run build`` if you want a shared secret on demo POSTs.
"""

from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    p = argparse.ArgumentParser(description="Bootstrap entitlements for PUBLIC_DEMO_USER_ID")
    p.add_argument("user_id", type=int, help="users.id for the dedicated demo account")
    p.add_argument(
        "--letters",
        type=int,
        default=40,
        help="Letter credits to add (default 40)",
    )
    p.add_argument(
        "--mailings",
        type=int,
        default=15,
        help="Certified mail credits to add (default 15)",
    )
    p.add_argument(
        "--ai-rounds",
        type=int,
        default=10,
        dest="ai_rounds",
        help="AI rounds to add (default 10)",
    )
    args = p.parse_args()

    import auth
    import database as db

    if not (os.environ.get("DATABASE_URL") or "").strip():
        print("DATABASE_URL is not set. Add it to .env or the environment.", file=sys.stderr)
        return 2

    with db.get_db(dict_cursor=True) as (conn, cur):
        cur.execute("SELECT id, email, role FROM users WHERE id = %s", (args.user_id,))
        row = cur.fetchone()
    if not row:
        print(
            f"No user with id={args.user_id}. For the synthetic demo user run: "
            f"python scripts/ensure_public_demo_test_account.py",
            file=sys.stderr,
        )
        return 1

    auth.add_entitlements(
        args.user_id,
        ai_rounds=args.ai_rounds,
        letters=args.letters,
        mailings=args.mailings,
        source="public_demo_bootstrap",
        note="850 Lab public /demo fixture runner",
    )
    print("Updated entitlements for:", dict(row))
    print()
    print("If you pin the demo to this user, set on the API host:")
    print(f"  PUBLIC_DEMO_USER_ID={args.user_id}")
    print("Production-like deploys also need PUBLIC_DEMO_ENABLED=1.")
    print()
    print("Confirm fixture PDFs deploy with the app (repo paths under samples/).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
