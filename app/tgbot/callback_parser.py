from dataclasses import dataclass
from enum import StrEnum

from app.models import BotKey


class UICallbackKind(StrEnum):
    MAIN_MENU = "menu"
    BOT_LIST = "bots"
    BOT_DETAIL = "detail"
    BOT_TOGGLE = "toggle"
    HABIT = "habit"
    SPORT = "sport"
    SETTINGS = "settings"
    REPORTS = "reports"
    HELP = "help"
    CONSENT_YES = "consent:yes"
    CONSENT_NO = "consent:no"


class HabitAction(StrEnum):
    LIST = "list"
    NEW = "new"
    DETAIL = "detail"
    TOGGLE = "toggle"
    CONFIRM = "confirm"
    CANCEL = "cancel"


class SportAction(StrEnum):
    MENU = "menu"
    LIST = "list"
    NEW = "new"
    DETAIL = "detail"
    TOGGLE = "toggle"
    CONFIRM = "confirm"
    CANCEL = "cancel"


class ReportAction(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


class SettingsAction(StrEnum):
    MENU = "menu"
    TIMEZONE = "timezone"
    NOTIFICATIONS_TOGGLE = "notifications_toggle"
    QUIET_HOURS = "quiet_hours"
    QUIET_HOURS_OFF = "quiet_hours_off"


class ReminderAction(StrEnum):
    DONE = "d"
    NOT_DONE = "n"
    SNOOZE = "s"
    SKIP = "x"


@dataclass(frozen=True)
class UICallback:
    kind: UICallbackKind
    bot_key: BotKey | None = None
    habit_action: HabitAction | None = None
    habit_id: int | None = None
    sport_action: SportAction | None = None
    sport_plan_id: int | None = None
    report_action: ReportAction | None = None
    settings_action: SettingsAction | None = None


@dataclass(frozen=True)
class ReminderCallback:
    event_id: int
    action: ReminderAction
    minutes: int | None = None


UI_PREFIX = "ui:"
REMINDER_PREFIX = "r:"


def format_ui(kind: UICallbackKind, bot_key: BotKey | None = None) -> str:
    if bot_key is None:
        return f"{UI_PREFIX}{kind.value}"
    return f"{UI_PREFIX}{kind.value}:{bot_key.value}"


def format_habit_ui(action: HabitAction, habit_id: int | None = None) -> str:
    if habit_id is None:
        return f"{UI_PREFIX}{UICallbackKind.HABIT.value}:{action.value}"
    return f"{UI_PREFIX}{UICallbackKind.HABIT.value}:{action.value}:{habit_id}"


def format_sport_ui(action: SportAction, sport_plan_id: int | None = None) -> str:
    if sport_plan_id is None:
        return f"{UI_PREFIX}{UICallbackKind.SPORT.value}:{action.value}"
    return f"{UI_PREFIX}{UICallbackKind.SPORT.value}:{action.value}:{sport_plan_id}"


def format_report_ui(action: ReportAction) -> str:
    return f"{UI_PREFIX}{UICallbackKind.REPORTS.value}:{action.value}"


def format_settings_ui(action: SettingsAction) -> str:
    return f"{UI_PREFIX}{UICallbackKind.SETTINGS.value}:{action.value}"


def format_reminder(event_id: int, action: ReminderAction, minutes: int | None = None) -> str:
    if action is ReminderAction.SNOOZE and minutes is not None:
        return f"{REMINDER_PREFIX}{event_id}:{action.value}{minutes}"
    return f"{REMINDER_PREFIX}{event_id}:{action.value}"


def parse_ui(data: str) -> UICallback | None:
    if not data.startswith(UI_PREFIX):
        return None
    rest = data[len(UI_PREFIX) :]
    if ":" in rest and rest in UICallbackKind:
        return UICallback(kind=UICallbackKind(rest))
    parts = rest.split(":")
    if not parts or parts[0] not in UICallbackKind:
        return None
    kind = UICallbackKind(parts[0])
    bot_key: BotKey | None = None
    if kind in (UICallbackKind.BOT_DETAIL, UICallbackKind.BOT_TOGGLE):
        if len(parts) < 2:
            return None
        try:
            bot_key = BotKey(parts[1])
        except ValueError:
            return None
    habit_action: HabitAction | None = None
    habit_id: int | None = None
    if kind is UICallbackKind.HABIT:
        if len(parts) < 2:
            return None
        try:
            habit_action = HabitAction(parts[1])
        except ValueError:
            return None
        if habit_action in (HabitAction.DETAIL, HabitAction.TOGGLE):
            if len(parts) < 3:
                return None
            try:
                habit_id = int(parts[2])
            except ValueError:
                return None
    sport_action: SportAction | None = None
    sport_plan_id: int | None = None
    if kind is UICallbackKind.SPORT:
        if len(parts) < 2:
            return None
        try:
            sport_action = SportAction(parts[1])
        except ValueError:
            return None
        if sport_action in (SportAction.DETAIL, SportAction.TOGGLE):
            if len(parts) < 3:
                return None
            try:
                sport_plan_id = int(parts[2])
            except ValueError:
                return None
    report_action: ReportAction | None = None
    if kind is UICallbackKind.REPORTS:
        if len(parts) >= 2:
            try:
                report_action = ReportAction(parts[1])
            except ValueError:
                return None
    settings_action: SettingsAction | None = None
    if kind is UICallbackKind.SETTINGS:
        if len(parts) >= 2:
            try:
                settings_action = SettingsAction(parts[1])
            except ValueError:
                return None
    return UICallback(
        kind=kind,
        bot_key=bot_key,
        habit_action=habit_action,
        habit_id=habit_id,
        sport_action=sport_action,
        sport_plan_id=sport_plan_id,
        report_action=report_action,
        settings_action=settings_action,
    )


def parse_reminder(data: str) -> ReminderCallback | None:
    if not data.startswith(REMINDER_PREFIX):
        return None
    parts = data[len(REMINDER_PREFIX) :].split(":")
    if len(parts) != 2:
        return None
    try:
        event_id = int(parts[0])
    except ValueError:
        return None

    action_part = parts[1]
    minutes: int | None = None
    if action_part.startswith(ReminderAction.SNOOZE.value) and len(action_part) > 1:
        action = ReminderAction.SNOOZE
        try:
            minutes = int(action_part[len(ReminderAction.SNOOZE.value) :])
        except ValueError:
            return None
        if minutes <= 0:
            return None
    elif action_part in ReminderAction:
        action = ReminderAction(action_part)
    else:
        return None

    return ReminderCallback(event_id=event_id, action=action, minutes=minutes)


def parse(data: str) -> UICallback | ReminderCallback | None:
    ui = parse_ui(data)
    if ui is not None:
        return ui
    return parse_reminder(data)
