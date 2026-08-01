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
    SUPPRESSED = "suppressed"


class NotificationLogStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    DEFERRED_QUIET_HOURS = "deferred_quiet_hours"
    SUPPRESSED_DISABLED = "suppressed_disabled"
    SUPPRESSED_BOT_DISABLED = "suppressed_bot_disabled"
    SUPPRESSED_USER_INACTIVE = "suppressed_user_inactive"
    SUPPRESSED_CONSENT_MISSING = "suppressed_consent_missing"


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


class ConsentRequirement(StrEnum):
    NONE = "none"
    RECOMMENDED = "recommended"
    REQUIRED = "required"


CONSENT_REQUIREMENTS: dict[BotKey, ConsentRequirement] = {
    BotKey.CORE: ConsentRequirement.NONE,
    BotKey.HABIT: ConsentRequirement.RECOMMENDED,
    BotKey.SPORT: ConsentRequirement.RECOMMENDED,
    BotKey.SUPPLEMENT: ConsentRequirement.RECOMMENDED,
    BotKey.STEP: ConsentRequirement.RECOMMENDED,
    BotKey.ASSESSMENT: ConsentRequirement.REQUIRED,
    BotKey.MEDICATION: ConsentRequirement.REQUIRED,
}


def consent_requirement_for(bot_key: BotKey) -> ConsentRequirement:
    return CONSENT_REQUIREMENTS[bot_key]


__all__ = [
    "BotKey",
    "ConsentRequirement",
    "NotificationLogStatus",
    "ReminderStatus",
    "ResponseType",
    "consent_requirement_for",
]
