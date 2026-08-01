from app.models import BotKey

WELCOME = (
    "Merhaba 👋\n\n"
    "Ben RutinBot.\n\n"
    "Günlük rutinlerini, sporunu, supplementlerini, adım sayını ve ilaç "
    "takibini yönetmene yardımcı olabilirim.\n\n"
    "Ne yapmak istersin?"
)

BOT_LIST_HEADER = "Botlar:\n\n{BOT_LIST}\n\nBir bot seç:"

BOT_LIST_ITEM = "{status} {label}"

BOT_LIST_ITEM_ACTIVE = "✅"
BOT_LIST_ITEM_INACTIVE = "⬜"

BOT_DETAIL = "{name} Botu\n\nDurum: {status}\n\nNe yapmak istersin?"

BOT_STATUS_ACTIVE = "Aktif"
BOT_STATUS_INACTIVE = "Kapalı"

CORE_BOT_CANNOT_BE_DISABLED = "Genel Rutin Botu ana bottur ve kapatılamaz."

BOT_ACTIVATED = "{name} Botu açıldı. ✅"
BOT_DEACTIVATED = "{name} Botu kapatıldı."

HELP = (
    "RutinBot yardım 📖\n\n"
    "/start - Ana menüyü aç\n"
    "/botlar - Botları yönet\n"
    "/ayarlar - Ayarları göster\n"
    "/rapor - Raporları göster\n"
    "/yardim - Bu yardım menüsü"
)

SETTINGS_STUB = "Ayarlar menüsü Faz 1'de gelecek. ⏳"
REPORT_STUB = "Raporlar menüsü Faz 1'de gelecek. ⏳"

BOT_KEYS_TR: dict[BotKey, str] = {
    BotKey.CORE: "Genel Rutin",
    BotKey.HABIT: "Rutin",
    BotKey.SPORT: "Spor",
    BotKey.SUPPLEMENT: "Supplement",
    BotKey.STEP: "Adım",
    BotKey.ASSESSMENT: "Sağlık",
    BotKey.MEDICATION: "İlaç",
}

COMMANDS = [
    ("start", "Ana menüyü aç"),
    ("botlar", "Botları yönet"),
    ("ayarlar", "Ayarları göster"),
    ("rapor", "Raporları göster"),
    ("yardim", "Yardım menüsü"),
]
