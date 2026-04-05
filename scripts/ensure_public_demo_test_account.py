#!/usr/bin/env python3
"""
Ensure the synthetic public-demo user exists (fictional consumer — not for real sign-in).

Creates ``850lab.public.demo@internal.invalid`` if missing, sets display name to a clear
fictional label, and (on first create) grants starter entitlements inside
``public_demo_service._get_or_create_internal_public_demo_user_id``.

Usage (repo root; ``DATABASE_URL`` in ``.env`` or environment):

  python scripts/ensure_public_demo_test_account.py

Add more letter/mail/AI credits if the demo user ran dry:

  python scripts/ensure_public_demo_test_account.py --top-up

To pin the API to this row explicitly:

  PUBLIC_DEMO_USER_ID=<id printed below>

Do not point ``PUBLIC_DEMO_USER_ID`` at a real customer.
"""

from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Create or repair the synthetic public /demo user (850lab.public.demo@internal.invalid)",
    )
    p.add_argument(
        "--top-up",
        action="store_true",
        help="Add starter ai_rounds/letters/mailings again (adds to current balance)",
    )
    args = p.parse_args()

    if not (os.environ.get("DATABASE_URL") or "").strip():
        print("DATABASE_URL is not set. Add it to .env or the environment.", file=sys.stderr)
        return 2

    from services.public_demo_service import ensure_public_demo_test_account

    try:
        uid, email = ensure_public_demo_test_account(top_up_entitlements=args.top_up)
    except RuntimeError as ex:
        print(ex, file=sys.stderr)
        return 1

    print("Synthetic public demo user is ready:")
    print(f"  users.id   = {uid}")
    print(f"  email      = {email}")
    print("  display    = fictional label in DB (not a real person)")
    print()
    print("Optional: set PUBLIC_DEMO_USER_ID on the API host to this id if you do not rely on auto-resolve.")
    print("Production-like deploys still need PUBLIC_DEMO_ENABLED=1 for /api/public/demo/*.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
