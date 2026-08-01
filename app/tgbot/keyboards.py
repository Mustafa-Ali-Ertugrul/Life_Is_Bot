from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import BotPreference
from app.tgbot.callback_parser import UICallbackKind, format_ui
from app.tgbot.messages import BOT_KEYS_TR


def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("BotlarÄ± YÃ¶net", callback_data=format_ui(UICallbackKind.BOT_LIST))],
        [InlineKeyboardButton("Ayarlar", callback_data=format_ui(UICallbackKind.SETTINGS))],
        [InlineKeyboardButton("Raporlar", callback_data=format_ui(UICallbackKind.REPORTS))],
        [InlineKeyboardButton("YardÄ±m", callback_data=format_ui(UICallbackKind.HELP))],
    ]
    return InlineKeyboardMarkup(keyboard)


def consent_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "OnaylÄ±yorum âœ…", callback_data=format_ui(UICallbackKind.CONSENT_YES)
            ),
            InlineKeyboardButton("HayÄ±r", callback_data=format_ui(UICallbackKind.CONSENT_NO)),
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
        [InlineKeyboardButton("â—€ï¸ Geri", callback_data=format_ui(UICallbackKind.MAIN_MENU))]
    )
    return InlineKeyboardMarkup(keyboard)


def bot_detail(preference: BotPreference, can_toggle: bool) -> InlineKeyboardMarkup:
    bot_key = preference.bot_key_enum
    keyboard: list[list[InlineKeyboardButton]] = []
    if can_toggle:
        toggle_label = "Botu Kapat" if preference.enabled else "Botu AÃ§"
        keyboard.append(
            [
                InlineKeyboardButton(
                    toggle_label,
                    callback_data=format_ui(UICallbackKind.BOT_TOGGLE, bot_key),
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton("â—€ï¸ Geri", callback_data=format_ui(UICallbackKind.BOT_LIST))]
    )
    return InlineKeyboardMarkup(keyboard)


def back_to_bots() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("â—€ï¸ Geri", callback_data=format_ui(UICallbackKind.BOT_LIST))]]
    )
