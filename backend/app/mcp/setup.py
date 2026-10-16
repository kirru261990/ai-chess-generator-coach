"""Set the connector's login password: `cd backend && uv run python -m app.mcp.setup`.

The password is read from a hidden prompt (never an argument or an environment variable), stored only as a scrypt hash in the
local auth database, and never printed. Running it again changes the password and clears a lock-out. Existing tokens stay valid
until they expire; to sign everything out, delete data/mcp_auth.sqlite3 and set the password again."""

from __future__ import annotations

import getpass
import sys

from app.mcp import auth


def main() -> int:
    conn = auth.connect()
    again = auth.password_is_set(conn)
    print(f"{'Changing' if again else 'Choosing'} the chat connector password (at least {auth.MIN_PASSWORD} characters).")
    first = getpass.getpass("Password: ")
    if getpass.getpass("Again: ") != first:
        print("The two did not match. Nothing was changed.", file=sys.stderr)
        return 1
    try:
        auth.set_password(conn, first)
    except ValueError as e:
        print(f"{e}. Nothing was changed.", file=sys.stderr)
        return 1
    print(f"Saved (hashed) in {auth.db_path()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
