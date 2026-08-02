from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import (
    BotPreference,
    Habit,
    MedicationPlan,
    SportPlan,
    StepSettings,
    SupplementPlan,
    User,
)
from app.tgbot.callback_parser import (
    HabitAction,
    MedicationAction,
    ReportAction,
    SettingsAction,
    SportAction,
    StepAction,
    SupplementAction,
    UICallbackKind,
    format_habit_ui,
    format_medication_ui,
    format_report_ui,
    format_settings_ui,
    format_sport_ui,
    format_step_ui,
    format_supplement_ui,
    format_ui,
)
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


def sport_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📋 Planlarım", callback_data=format_sport_ui(SportAction.LIST))],
        [InlineKeyboardButton("➕ Yeni Plan Ekle", callback_data=format_sport_ui(SportAction.NEW))],
        [InlineKeyboardButton("◀️ Ana Menü", callback_data=format_ui(UICallbackKind.MAIN_MENU))],
    ]
    return InlineKeyboardMarkup(keyboard)


def sport_plan_list(plans: list[SportPlan]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for plan in plans:
        label = plan.sport_type
        keyboard.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=format_sport_ui(SportAction.DETAIL, plan.id),
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton("➕ Yeni Plan Ekle", callback_data=format_sport_ui(SportAction.NEW))]
    )
    keyboard.append(
        [InlineKeyboardButton("◀️ Ana Menü", callback_data=format_ui(UICallbackKind.MAIN_MENU))]
    )
    return InlineKeyboardMarkup(keyboard)


def sport_plan_detail(plan: SportPlan) -> InlineKeyboardMarkup:
    toggle_label = "Planı Kapat" if plan.is_active else "Planı Aç"
    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                toggle_label,
                callback_data=format_sport_ui(SportAction.TOGGLE, plan.id),
            )
        ],
        [InlineKeyboardButton("◀️ Geri", callback_data=format_sport_ui(SportAction.LIST))],
    ]
    return InlineKeyboardMarkup(keyboard)


def sport_confirm() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Onayla ✅", callback_data=format_sport_ui(SportAction.CONFIRM)),
            InlineKeyboardButton("Vazgeç ❌", callback_data=format_sport_ui(SportAction.CANCEL)),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def supplement_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "📋 Planlarım", callback_data=format_supplement_ui(SupplementAction.LIST)
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Yeni Plan Ekle", callback_data=format_supplement_ui(SupplementAction.NEW)
            )
        ],
        [InlineKeyboardButton("◀️ Ana Menü", callback_data=format_ui(UICallbackKind.MAIN_MENU))],
    ]
    return InlineKeyboardMarkup(keyboard)


def supplement_plan_list(plans: list[SupplementPlan]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for plan in plans:
        label = plan.name
        keyboard.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=format_supplement_ui(SupplementAction.DETAIL, plan.id),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Yeni Plan Ekle", callback_data=format_supplement_ui(SupplementAction.NEW)
            )
        ]
    )
    keyboard.append(
        [InlineKeyboardButton("◀️ Ana Menü", callback_data=format_ui(UICallbackKind.MAIN_MENU))]
    )
    return InlineKeyboardMarkup(keyboard)


def supplement_plan_detail(plan: SupplementPlan) -> InlineKeyboardMarkup:
    toggle_label = "Pasif Et" if plan.is_active else "Aktif Et"
    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                toggle_label,
                callback_data=format_supplement_ui(SupplementAction.TOGGLE, plan.id),
            )
        ],
        [InlineKeyboardButton("◀️ Geri", callback_data=format_supplement_ui(SupplementAction.LIST))],
    ]
    return InlineKeyboardMarkup(keyboard)


def supplement_confirm() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Evet ✅", callback_data=format_supplement_ui(SupplementAction.CONFIRM)
            ),
            InlineKeyboardButton(
                "İptal ❌", callback_data=format_supplement_ui(SupplementAction.CANCEL)
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def medication_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "📋 Planlarım", callback_data=format_medication_ui(MedicationAction.LIST)
            )
        ],
        [
            InlineKeyboardButton(
                "➕ Yeni İlaç Ekle", callback_data=format_medication_ui(MedicationAction.NEW)
            )
        ],
        [InlineKeyboardButton("◀️ Ana Menü", callback_data=format_ui(UICallbackKind.MAIN_MENU))],
    ]
    return InlineKeyboardMarkup(keyboard)


def medication_plan_list(plans: list[MedicationPlan]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for plan in plans:
        label = plan.name
        keyboard.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=format_medication_ui(MedicationAction.DETAIL, plan.id),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Yeni İlaç Ekle", callback_data=format_medication_ui(MedicationAction.NEW)
            )
        ]
    )
    keyboard.append(
        [InlineKeyboardButton("◀️ Ana Menü", callback_data=format_ui(UICallbackKind.MAIN_MENU))]
    )
    return InlineKeyboardMarkup(keyboard)


def medication_plan_detail(plan: MedicationPlan) -> InlineKeyboardMarkup:
    toggle_label = "Pasif Et" if plan.is_active else "Aktif Et"
    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                toggle_label,
                callback_data=format_medication_ui(MedicationAction.TOGGLE, plan.id),
            )
        ],
        [InlineKeyboardButton("◀️ Geri", callback_data=format_medication_ui(MedicationAction.LIST))],
    ]
    return InlineKeyboardMarkup(keyboard)


def medication_confirm() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Evet ✅", callback_data=format_medication_ui(MedicationAction.CONFIRM)
            ),
            InlineKeyboardButton(
                "İptal ❌", callback_data=format_medication_ui(MedicationAction.CANCEL)
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def step_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📝 Adım Gir", callback_data=format_step_ui(StepAction.LOG)),
            InlineKeyboardButton("⚙️ Ayarlar", callback_data=format_step_ui(StepAction.SETTINGS)),
        ],
        [InlineKeyboardButton("◀️ Ana Menü", callback_data=format_ui(UICallbackKind.MAIN_MENU))],
    ]
    return InlineKeyboardMarkup(keyboard)


def step_settings_detail(settings: StepSettings) -> InlineKeyboardMarkup:
    toggle_label = "⏸️ Pasif Et" if settings.is_active else "▶️ Aktif Et"
    keyboard = [
        [
            InlineKeyboardButton(
                "🎯 Hedef Değiştir", callback_data=format_step_ui(StepAction.GOAL)
            ),
            InlineKeyboardButton("⏰ Saat Değiştir", callback_data=format_step_ui(StepAction.TIME)),
        ],
        [
            InlineKeyboardButton(
                "📅 Günleri Değiştir", callback_data=format_step_ui(StepAction.DAYS)
            ),
            InlineKeyboardButton(toggle_label, callback_data=format_step_ui(StepAction.TOGGLE)),
        ],
        [InlineKeyboardButton("◀️ Geri", callback_data=format_step_ui(StepAction.MENU))],
    ]
    return InlineKeyboardMarkup(keyboard)


def report_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📅 Bugün", callback_data=format_report_ui(ReportAction.DAILY)),
            InlineKeyboardButton(
                "📈 Haftalık", callback_data=format_report_ui(ReportAction.WEEKLY)
            ),
        ],
        [InlineKeyboardButton("◀️ Ana Menü", callback_data=format_ui(UICallbackKind.MAIN_MENU))],
    ]
    return InlineKeyboardMarkup(keyboard)


def settings_menu(user: User) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                "🌍 Timezone Değiştir",
                callback_data=format_settings_ui(SettingsAction.TIMEZONE),
            )
        ],
        [
            InlineKeyboardButton(
                "🔔 Bildirimleri Değiştir",
                callback_data=format_settings_ui(SettingsAction.NOTIFICATIONS_TOGGLE),
            )
        ],
    ]
    if user.quiet_hours_enabled:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🌙 Sessiz Saatleri Kapat",
                    callback_data=format_settings_ui(SettingsAction.QUIET_HOURS_OFF),
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                "🌙 Sessiz Saatleri Ayarla",
                callback_data=format_settings_ui(SettingsAction.QUIET_HOURS),
            )
        ]
    )
    keyboard.append(
        [InlineKeyboardButton("◀️ Geri", callback_data=format_ui(UICallbackKind.MAIN_MENU))]
    )
    return InlineKeyboardMarkup(keyboard)
