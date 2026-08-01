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
    "ReminderStatus",
    "ResponseType",
    "consent_requirement_for",
]
