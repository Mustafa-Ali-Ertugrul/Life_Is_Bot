from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import BotPreference, Habit
from app.tgbot.callback_parser import HabitAction, UICallbackKind, format_habit_ui, format_ui
from app.tgbot.messages import BOT_KEYS_TR


def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Botları Yönet", callback_data=format_ui(UICallbackKind.BOT_LIST))],
        [InlineKeyboardButton("Ayarlar", callback_data=format_ui(UICallbackKind.SETTINGS))],
        [InlineKeyboardButton("Raporlar", callback_data=format_ui(UICallbackKind.REPORTS))],
        [InlineKeyboardButton("Yardım", callback_data=format_ui(UICallbackKind.HELP))],
    ]
    return InlineKeyboardMarkup(keyboard)


def consent_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Onaylıyorum ✅", callback_data=format_ui(UICallbackKind.CONSENT_YES)
            ),
            InlineKeyboardButton("Hayır", callback_data=format_ui(UICallbackKind.CONSENT_NO)),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def bot_list(preferences: list[BotPreference]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for preference in preferences:
        bot_key = preference.bot_key_enum
        label = BOT_KEYS_TR[bot_key]
        keyboard.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=format_ui(UICallbackKind.BOT_DETAIL, bot_key),
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton("◀️ Geri", callback_data=format_ui(UICallbackKind.MAIN_MENU))]
    )
    return InlineKeyboardMarkup(keyboard)


def bot_detail(preference: BotPreference, can_toggle: bool) -> InlineKeyboardMarkup:
    bot_key = preference.bot_key_enum
    keyboard: list[list[InlineKeyboardButton]] = []
    if can_toggle:
        toggle_label = "Botu Kapat" if preference.enabled else "Botu Aç"
        keyboard.append(
            [
                InlineKeyboardButton(
                    toggle_label,
                    callback_data=format_ui(UICallbackKind.BOT_TOGGLE, bot_key),
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton("◀️ Geri", callback_data=format_ui(UICallbackKind.BOT_LIST))]
    )
    return InlineKeyboardMarkup(keyboard)


def back_to_bots() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("◀️ Geri", callback_data=format_ui(UICallbackKind.BOT_LIST))]]
    )


def habit_list(habits: list[Habit]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for habit in habits:
        label = habit.name
        keyboard.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=format_habit_ui(HabitAction.DETAIL, habit.id),
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton("➕ Yeni Rutin", callback_data=format_habit_ui(HabitAction.NEW))]
    )
    keyboard.append(
        [InlineKeyboardButton("◀️ Ana Menü", callback_data=format_ui(UICallbackKind.MAIN_MENU))]
    )
    return InlineKeyboardMarkup(keyboard)


def habit_detail(habit: Habit) -> InlineKeyboardMarkup:
    toggle_label = "Rutini Kapat" if habit.is_active else "Rutini Aç"
    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                toggle_label,
                callback_data=format_habit_ui(HabitAction.TOGGLE, habit.id),
            )
        ],
        [InlineKeyboardButton("◀️ Geri", callback_data=format_habit_ui(HabitAction.LIST))],
    ]
    return InlineKeyboardMarkup(keyboard)


def habit_confirm() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Onayla ✅", callback_data=format_habit_ui(HabitAction.CONFIRM)),
            InlineKeyboardButton("Vazgeç ❌", callback_data=format_habit_ui(HabitAction.CANCEL)),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
