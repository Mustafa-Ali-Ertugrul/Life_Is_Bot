from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import BotPreference
from app.telegram.messages import BOT_KEYS_TR

CALLBACK_MAIN_MENU = "menu:main"
CALLBACK_BOT_LIST = "menu:bots"
CALLBACK_BOT_TOGGLE = "toggle:{bot_key}"
CALLBACK_BOT_DETAIL = "detail:{bot_key}"


def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Botları Yönet", callback_data=CALLBACK_BOT_LIST),
        ],
        [
            InlineKeyboardButton("Ayarlar", callback_data="stub:settings"),
        ],
        [
            InlineKeyboardButton("Raporlar", callback_data="stub:reports"),
        ],
        [
            InlineKeyboardButton("Yardım", callback_data="stub:help"),
        ],
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
                    callback_data=CALLBACK_BOT_DETAIL.format(bot_key=bot_key.value),
                )
            ]
        )
    keyboard.append([InlineKeyboardButton("◀️ Geri", callback_data=CALLBACK_MAIN_MENU)])
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
                    callback_data=CALLBACK_BOT_TOGGLE.format(bot_key=bot_key.value),
                )
            ]
        )
    keyboard.append([InlineKeyboardButton("◀️ Geri", callback_data=CALLBACK_BOT_LIST)])
    return InlineKeyboardMarkup(keyboard)


def back_to_bots() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data=CALLBACK_BOT_LIST)]])
