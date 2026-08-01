from app.models import BotKey
from app.tgbot.callback_parser import (
    HabitAction,
    ReminderAction,
    ReminderCallback,
    ReportAction,
    SettingsAction,
    UICallback,
    UICallbackKind,
    format_habit_ui,
    format_reminder,
    format_report_ui,
    format_settings_ui,
    format_ui,
    parse,
    parse_reminder,
    parse_ui,
)


def test_format_ui_menu() -> None:
    assert format_ui(UICallbackKind.MAIN_MENU) == "ui:menu"
    assert format_ui(UICallbackKind.BOT_TOGGLE, BotKey.SPORT) == "ui:toggle:sport_bot"


def test_parse_ui_detail() -> None:
    parsed = parse_ui("ui:detail:sport_bot")

    assert parsed is not None
    assert parsed.kind is UICallbackKind.BOT_DETAIL
    assert parsed.bot_key is BotKey.SPORT


def test_parse_ui_unknown_kind_returns_none() -> None:
    assert parse_ui("ui:unknown") is None
    assert parse_ui("ui:detail") is None
    assert parse_ui("ui:detail:bilinmeyen_bot") is None


def test_parse_ui_consent() -> None:
    parsed = parse_ui("ui:consent:yes")

    assert parsed is not None
    assert parsed.kind is UICallbackKind.CONSENT_YES


def test_format_habit_ui() -> None:
    assert format_habit_ui(HabitAction.LIST) == "ui:habit:list"
    assert format_habit_ui(HabitAction.NEW) == "ui:habit:new"
    assert format_habit_ui(HabitAction.DETAIL, 42) == "ui:habit:detail:42"
    assert format_habit_ui(HabitAction.TOGGLE, 7) == "ui:habit:toggle:7"


def test_parse_ui_habit_actions() -> None:
    parsed_list = parse_ui("ui:habit:list")
    assert parsed_list is not None
    assert parsed_list.kind is UICallbackKind.HABIT
    assert parsed_list.habit_action is HabitAction.LIST
    assert parsed_list.habit_id is None

    parsed_detail = parse_ui("ui:habit:detail:42")
    assert parsed_detail is not None
    assert parsed_detail.habit_action is HabitAction.DETAIL
    assert parsed_detail.habit_id == 42


def test_parse_ui_habit_invalid() -> None:
    assert parse_ui("ui:habit") is None
    assert parse_ui("ui:habit:detail") is None
    assert parse_ui("ui:habit:detail:abc") is None
    assert parse_ui("ui:habit:bilinmeyen") is None


def test_format_report_ui() -> None:
    assert format_report_ui(ReportAction.DAILY) == "ui:reports:daily"
    assert format_report_ui(ReportAction.WEEKLY) == "ui:reports:weekly"


def test_format_settings_ui() -> None:
    assert format_settings_ui(SettingsAction.MENU) == "ui:settings:menu"
    assert format_settings_ui(SettingsAction.TIMEZONE) == "ui:settings:timezone"
    assert (
        format_settings_ui(SettingsAction.NOTIFICATIONS_TOGGLE)
        == "ui:settings:notifications_toggle"
    )
    assert format_settings_ui(SettingsAction.QUIET_HOURS) == "ui:settings:quiet_hours"
    assert format_settings_ui(SettingsAction.QUIET_HOURS_OFF) == "ui:settings:quiet_hours_off"


def test_parse_ui_settings_actions() -> None:
    parsed_root = parse_ui("ui:settings")
    assert parsed_root is not None
    assert parsed_root.kind is UICallbackKind.SETTINGS
    assert parsed_root.settings_action is None

    parsed_menu = parse_ui("ui:settings:menu")
    assert parsed_menu is not None
    assert parsed_menu.kind is UICallbackKind.SETTINGS
    assert parsed_menu.settings_action is SettingsAction.MENU

    parsed_tz = parse_ui("ui:settings:timezone")
    assert parsed_tz is not None
    assert parsed_tz.kind is UICallbackKind.SETTINGS
    assert parsed_tz.settings_action is SettingsAction.TIMEZONE

    parsed_toggle = parse_ui("ui:settings:notifications_toggle")
    assert parsed_toggle is not None
    assert parsed_toggle.settings_action is SettingsAction.NOTIFICATIONS_TOGGLE

    parsed_qh = parse_ui("ui:settings:quiet_hours")
    assert parsed_qh is not None
    assert parsed_qh.settings_action is SettingsAction.QUIET_HOURS

    parsed_qh_off = parse_ui("ui:settings:quiet_hours_off")
    assert parsed_qh_off is not None
    assert parsed_qh_off.settings_action is SettingsAction.QUIET_HOURS_OFF


def test_parse_ui_settings_invalid() -> None:
    assert parse_ui("ui:settings:bilinmeyen") is None


def test_format_settings_roundtrip() -> None:
    for action in SettingsAction:
        parsed = parse_ui(format_settings_ui(action))
        assert parsed is not None
        assert parsed.settings_action is action


def test_parse_ui_reports_actions() -> None:
    parsed_root = parse_ui("ui:reports")
    assert parsed_root is not None
    assert parsed_root.kind is UICallbackKind.REPORTS
    assert parsed_root.report_action is None

    parsed_daily = parse_ui("ui:reports:daily")
    assert parsed_daily is not None
    assert parsed_daily.kind is UICallbackKind.REPORTS
    assert parsed_daily.report_action is ReportAction.DAILY

    parsed_weekly = parse_ui("ui:reports:weekly")
    assert parsed_weekly is not None
    assert parsed_weekly.report_action is ReportAction.WEEKLY


def test_parse_ui_reports_invalid() -> None:
    assert parse_ui("ui:reports:aylik") is None

    parsed_extra = parse_ui("ui:reports:daily:extra")
    assert parsed_extra is not None
    assert parsed_extra.report_action is ReportAction.DAILY


def test_parse_reminder_done() -> None:
    parsed = parse_reminder("r:9001:d")

    assert parsed is not None
    assert parsed.event_id == 9001
    assert parsed.action is ReminderAction.DONE
    assert parsed.minutes is None


def test_parse_reminder_snooze() -> None:
    parsed = parse_reminder("r:9001:s10")

    assert parsed is not None
    assert parsed.action is ReminderAction.SNOOZE
    assert parsed.minutes == 10


def test_parse_reminder_invalid() -> None:
    assert parse_reminder("r:abc:d") is None
    assert parse_reminder("r:9001:z") is None
    assert parse_reminder("r:9001:s0") is None
    assert parse_reminder("r:9001") is None
    assert parse_reminder("9001:d") is None


def test_format_reminder_roundtrip() -> None:
    data = format_reminder(123, ReminderAction.NOT_DONE)
    parsed = parse_reminder(data)

    assert parsed is not None
    assert parsed.event_id == 123
    assert parsed.action is ReminderAction.NOT_DONE

    snooze_data = format_reminder(123, ReminderAction.SNOOZE, minutes=15)
    snooze = parse_reminder(snooze_data)
    assert snooze is not None
    assert snooze.minutes == 15


def test_parse_routes_by_namespace() -> None:
    ui = parse("ui:bots")
    reminder = parse("r:42:d")

    assert isinstance(ui, UICallback)
    assert ui.kind is UICallbackKind.BOT_LIST
    assert isinstance(reminder, ReminderCallback)
    assert reminder.event_id == 42


def test_callback_data_within_telegram_limit() -> None:
    longest = format_reminder(9_999_999, ReminderAction.SNOOZE, minutes=999)
    assert len(longest) <= 64
