"""Diagnose timestamp formats in `reminder_events`.

Read-only. Prints a breakdown of naive vs aware timestamps across
`scheduled_at`, `notify_after`, and `created_at` per status, plus a list
of future-facing (pending) rows whose `scheduled_at` or `notify_after` is
naive. Used by #29 to decide whether a data-fix migration is required.

Usage:
    python scripts/diagnose_timestamps.py [sqlite_url]

    sqlite_url defaults to settings.database_url (e.g.
    sqlite+aiosqlite:///life_is_bot.db). A plain path or file:// URL is
    also accepted; mdbt connections use the sync sqlite3 driver.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from app.core.config import settings

PENDING_STATUSES = ("scheduled", "snoozed")
TERMINAL_STATUSES = (
    "positive",
    "negative",
    "no_response",
    "cancelled",
    "suppressed",
    "notified",
)

PENDING = "pending"
TERMINAL = "terminal"


def _is_aware(value: str | None) -> bool:
    if value is None:
        return False
    return value.endswith(("+00:00", "Z", "+01:00", "+02:00", "+03:00", "-00:00", "-01:00"))


def _classify(status: str) -> str:
    if status in PENDING_STATUSES:
        return PENDING
    if status in TERMINAL_STATUSES:
        return TERMINAL
    return "other"


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
        for col in ("scheduled_at", "notify_after", "created_at"):
            if col not in cols:
                continue
            naive = conn.execute(
                f"SELECT COUNT(*) FROM reminder_events "
                f"WHERE {col} IS NOT NULL AND {col} NOT LIKE '%+%' "
                f"AND {col} NOT LIKE '%Z%'"
            ).fetchone()[0]
            aware = conn.execute(
                f"SELECT COUNT(*) FROM reminder_events "
                f"WHERE {col} IS NOT NULL AND ({col} LIKE '%+%' OR {col} LIKE '%Z%')"
            ).fetchone()[0]
            print(f"  {col:<14} naive={naive:<5} aware={aware}")

        print("\n== format x status ==")
        print(f"  {'status':<14} {'class':<9} {'naive':<6} {'aware'}")
        for (status,) in conn.execute(
            "SELECT DISTINCT status FROM reminder_events ORDER BY status"
        ).fetchall():
            if status is None:
                continue
            naive = conn.execute(
                "SELECT COUNT(*) FROM reminder_events WHERE status = ? AND "
                "scheduled_at IS NOT NULL AND scheduled_at NOT LIKE '%+%' "
                "AND scheduled_at NOT LIKE '%Z%'",
                (status,),
            ).fetchone()[0]
            aware = conn.execute(
                "SELECT COUNT(*) FROM reminder_events WHERE status = ? "
                "AND scheduled_at IS NOT NULL "
                "AND (scheduled_at LIKE '%+%' OR scheduled_at LIKE '%Z%')",
                (status,),
            ).fetchone()[0]
            print(f"  {status:<14} {_classify(status):<9} {naive:<6} {aware}")

        pending_cols = [c for c in ("scheduled_at", "notify_after") if c in cols]
        pending_rows = conn.execute(
            "SELECT id, user_id, status, scheduled_at, "
            + ", ".join(pending_cols)
            + " FROM reminder_events WHERE status IN ('scheduled', 'snoozed') "
            "AND (scheduled_at NOT LIKE '%+%' OR notify_after NOT LIKE '%+%') "
            "ORDER BY id"
        ).fetchall()

        print("\n== pending naive rows ==")
        if not pending_rows:
            print("  (none - no data-fix migration required)")
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
        print(f"  pending rows (scheduled/snoozed): {pending_total}")
        print(f"  pending naive rows needing fix: {len(pending_rows)}")
        if pending_rows:
            print("  -> data-fix migration is REQUIRED")
        else:
            print("  -> data-fix migration NOT required (policy + tests only)")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
