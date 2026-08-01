from enum import StrEnum


class BotKey(StrEnum):
    CORE = "core_bot"
    HABIT = "habit_bot"
    SPORT = "sport_bot"
    SUPPLEMENT = "supplement_bot"
    STEP = "step_bot"
    ASSESSMENT = "assessment_bot"
    MEDICATION = "medication_bot"


class ReminderStatus(StrEnum):
    SCHEDULED = "scheduled"
    NOTIFIED = "notified"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    SNOOZED = "snoozed"
    NO_RESPONSE = "no_response"
    CANCELLED = "cancelled"


class ResponseType(StrEnum):
    DONE = "done"
    NOT_DONE = "not_done"
    TAKEN = "taken"
    NOT_TAKEN = "not_taken"
    YES = "yes"
    NO = "no"
    PARTIAL = "partial"
    SNOOZED = "snoozed"
    SKIPPED = "skipped"


__all__ = ["BotKey", "ReminderStatus", "ResponseType"]
