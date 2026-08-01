# Datetime Policy

Defines how timestamps are stored, compared, and displayed across the
codebase. Adopted in **v0.3.2** (tracks #29).

## Storage

- **Canonical storage is naive UTC wall-clock.** SQLite stores datetimes
  as offset-less strings (`YYYY-MM-DD HH:MM:SS.ffffff`); the SQLAlchemy
  bind processor strips `tzinfo` from every value written through an ORM
  column (`DateTime(timezone=True)` is advisory only). Therefore the
  instant is represented by its UTC wall-clock components and the offset
  is implied.
- **Application layer is the source of truth.** All datetime columns
  (`scheduled_at`, `notify_after`, `created_at`, ...) must be built as
  aware values. `reminder_service` normalizes aware values to UTC
  (`_canonical_utc`) before writing; naive values are treated as UTC
  wall-clock.
- `scripts/diagnose_timestamps.py` prints the stored formats and pending
  rows for manual audit.

## Comparisons

- **Due queries compare UTC wall-clock only.** `find_due_events`
  normalizes an aware `now` to UTC before the query, so SQLite string
  ordering matches the stored UTC wall-clock values. Callers must pass an
  aware clock (`scheduler.jobs` uses `now_in(UTC)`).
- **Writes that affect scheduling must be UTC-aware**:
  - `scheduler.jobs.reminder_tick` → `now_in(UTC)`
  - snooze reschedule (`tgbot.callbacks`) → `now_in(UTC) + timedelta(...)`
  - habit events (`habit_service`) → `local_scheduled.astimezone(UTC)`
  - quiet-hours deferral (`notification_policy`) → `defer_until.astimezone(UTC)`

## Display

- **User timezone at the boundary.** Convert to the user's `timezone`
  (`get_user_timezone(user.timezone)`) only when showing a time to the
  user (`_scheduled_local_date`, reports).
- **Reports: `scheduled_local_date`.** A denormalized per-user local
  date used for grouping/dedupe (`dedupe_key`). It is derived from the
  canonical UTC value at write time and stored alongside the event.

## Legacy data

- Pre-v0.3.2 rows were already stored as offset-less strings. Rows
  written through `now_in()` (local app timezone) carry local wall-clock
  values; rows written through `astimezone(UTC)` carry UTC wall-clock
  values. `find_due_events` compares against UTC wall-clock, so pending
  rows from before this policy may be evaluated against a shifted clock.
  No automated data-fix migration is shipped; if a production audit
  (`scripts/diagnose_timestamps.py`) finds suspicious pending values,
  re-create those events or add a targeted migration.

## Guidance for code

- Always build aware datetimes (`datetime(..., tzinfo=UTC)` or
  `now_in(UTC)`) and let the ORM strip the offset at bind time.
- Never write a naive `datetime.now()` local wall-clock value to
  `scheduled_at` / `notify_after`.
- Test fixtures should pass UTC-aware values for pending columns.
