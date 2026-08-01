"""Audit pending timestamps in `reminder_events`.

Read-only. SQLite stores every datetime as an offset-less string
(`YYYY-MM-DD HH:MM:SS.ffffff`); the ORM strips tzinfo on bind, so naive
storage is the expected canonical form (UTC wall-clock). This script
reports the stored formats and lists future-facing (pending) rows so the
values can be eyeballed for plausibility.

Usage:
    python scripts/diagnose_timestamps.py [sqlite_url]

    sqlite_url defaults to settings.database_url (e.g.
    sqlite+aiosqlite:///life_is_bot.db). A plain path or file:// URL is
    also accepted; connections use the sync sqlite3 driver.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from app.core.config import settings

PENDING_STATUSES = ("scheduled", "snoozed")


def _is_naive_format(value: str | None) -> bool:
    if value is None:
        return False
    return not value.endswith(("Z", "+00:00", "+01:00", "+02:00", "+03:00", "-00:00"))


def _db_path(url: str) -> str:
    if url.startswith("sqlite"):
        # sqlite+aiosqlite:///path or sqlite:///path
        marker = "///"
        if marker in url:
            return url.split(marker, 1)[1]
        if ":" in url:
            return url.split(":", 1)[1]
    if url.startswith("file://"):
        return url[len("file://") :]
    return url


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else settings.database_url
    db_path = _db_path(url)
    path = Path(db_path).expanduser()

    if not path.exists():
        print(f"[skip] database not found: {path}")
        return 0

    conn = sqlite3.connect(str(path))
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(reminder_events)").fetchall()}

        print("== per-column format distribution ==")
        print("  (naive = offset-less string; expected for SQLite storage)")
        for col in ("scheduled_at", "notify_after", "created_at"):
            if col not in cols:
                continue
            total = conn.execute(
                f"SELECT COUNT(*) FROM reminder_events WHERE {col} IS NOT NULL"
            ).fetchone()[0]
            naive = conn.execute(
                f"SELECT COUNT(*) FROM reminder_events WHERE {col} IS NOT NULL AND "
                f"({col} NOT LIKE '%Z%' AND {col} NOT LIKE '%+%')"
            ).fetchone()[0]
            print(f"  {col:<14} total={total:<5} naive={naive}")

        pending_cols = [c for c in ("scheduled_at", "notify_after") if c in cols]
        pending_rows = conn.execute(
            "SELECT id, user_id, status, scheduled_at, "
            + ", ".join(pending_cols)
            + " FROM reminder_events WHERE status IN ('scheduled', 'snoozed') "
            "ORDER BY id"
        ).fetchall()

        print("\n== pending rows (scheduled/snoozed) ==")
        if not pending_rows:
            print("  (none)")
        else:
            user_tz = dict(conn.execute("SELECT id, timezone FROM users").fetchall())
            for row in pending_rows:
                event_id, user_id, status, scheduled_at = row[0], row[1], row[2], row[3]
                notify_after = row[4] if len(row) > 4 else None
                print(
                    f"  id={event_id} user={user_id} tz={user_tz.get(user_id)} "
                    f"status={status} scheduled_at={scheduled_at} "
                    f"notify_after={notify_after}"
                )

        print("\n== summary ==")
        total = conn.execute("SELECT COUNT(*) FROM reminder_events").fetchone()[0]
        pending_total = conn.execute(
            "SELECT COUNT(*) FROM reminder_events WHERE status IN ('scheduled', 'snoozed')"
        ).fetchone()[0]
        print(f"  total rows: {total}")
        print(f"  pending rows: {pending_total}")
        print(
            "  storage is expected to be naive UTC wall-clock (SQLite strips tz); "
            "no data-fix migration is required"
        )

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
