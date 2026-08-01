from app.models import BotKey

WELCOME = (
    "Merhaba 👋\n\n"
    "Ben RutinBot.\n\n"
    "Günlük rutinlerini, sporunu, supplementlerini, adım sayını ve ilaç "
    "takibini yönetmene yardımcı olabilirim.\n\n"
    "Ne yapmak istersin?"
)

CONSENT_TEXT = (
    "Başlamadan önce kısa bir bilgilendirme 📋\n\n"
    "• Bu bot sağlık ve rutin verilerini işleyebilir.\n"
    "• Verilerin bu sistemde saklanır ve sadece sana özel kullanılır.\n"
    "• Tıbbi teşhis koymaz.\n"
    "• Acil durumlarda mutlaka bir sağlık profesyoneline başvur.\n\n"
    "Devam etmek için onayını gerekiyor:"
)

CONSENT_GRANTED = "Onayın alındı, teşekkürler! ✅"
CONSENT_DENIED = (
    "Onay verilmediği için RutinBot kullanılamıyor. "
    "İstediğin zaman /start ile tekrar deneyebilirsin."
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
    "/rutin - Rutinlerini yönet\n"
    "/rutin_ekle - Yeni rutin ekle\n"
    "/ayarlar - Ayarları göster\n"
    "/rapor - Raporları göster\n"
    "/yardim - Bu yardım menüsü"
)

SETTINGS_HEADER = (
    "Ayarlar ⚙️\n\n"
    "Timezone: {timezone}\n"
    "Bildirimler: {notifications}\n"
    "Sessiz saatler: {quiet_hours}\n"
    "Dil: Türkçe"
)
SETTINGS_NOTIFICATIONS_ON = "Açık"
SETTINGS_NOTIFICATIONS_OFF = "Kapalı"
SETTINGS_QUIET_HOURS_NONE = "Kapalı"
SETTINGS_QUIET_HOURS_RANGE = "{start} - {end}"
SETTINGS_ASK_TIMEZONE = (
    "Yeni timezone'u IANA adıyla yaz (örn: Europe/Istanbul).\n\n"
    "/iptal ile vazgeçebilirsin."
)
SETTINGS_INVALID_TIMEZONE = "Geçersiz timezone. IANA adı kullan (örn: Europe/Istanbul)."
SETTINGS_TIMEZONE_UPDATED = "Timezone güncellendi: {timezone} ✅"
SETTINGS_ASK_QUIET_START = (
    "Sessiz saatlerin başlangıcı (HH:MM, örn: 23:00)?\n\n"
    "/iptal ile vazgeçebilirsin."
)
SETTINGS_ASK_QUIET_END = (
    "Sessiz saatlerin bitişi (HH:MM, örn: 07:00)?\n\n"
    "/iptal ile vazgeçebilirsin."
)
SETTINGS_INVALID_TIME = "Saat formatı geçersiz. HH:MM şeklinde yaz (örn: 23:00)."
SETTINGS_QUIET_HOURS_UPDATED = "Sessiz saatler ayarlandı: {start} - {end} 🌙"
SETTINGS_QUIET_HOURS_OFF = "Sessiz saatler kapatıldı."
SETTINGS_NOTIFICATIONS_ON_MSG = "Bildirimler açıldı. ✅"
SETTINGS_NOTIFICATIONS_OFF_MSG = "Bildirimler kapatıldı."
SETTINGS_CANCELLED = "Ayarlar iptal edildi."

REPORT_DAILY_TITLE = "Bugünkü özet 📊"
REPORT_WEEKLY_TITLE = "Bu hafta 📈"
REPORT_SUMMARY_LINES = (
    "Toplam rutin: {total}\n"
    "Tamamlanan: {completed}\n"
    "Kaçırılan: {missed}\n"
    "Yanıt verilmeyen: {unanswered}"
)
REPORT_COMPLETED_HEADER = "Tamamlananlar:"
REPORT_MISSED_HEADER = "Kaçırılanlar:"
REPORT_ITEM_COMPLETED = "✅ {label}"
REPORT_ITEM_MISSED = "❌ {label}"
REPORT_EMPTY = "Bu dönemde kayıtlı hatırlatma yok. 🕐"
REPORT_COMPLIANCE = "Uyum oranı: %{rate}"
REPORT_BEST_DAY = "En iyi gün: {day}"
REPORT_WEAKEST_DAY = "En zayıf gün: {day}"

WEEKDAY_NAMES_TR: dict[int, str] = {
    1: "Pazartesi",
    2: "Salı",
    3: "Çarşamba",
    4: "Perşembe",
    5: "Cuma",
    6: "Cumartesi",
    7: "Pazar",
}

HABIT_LIST_HEADER = "Rutinlerin:\n\n{BOT_LIST}\n\nBir rutin seç veya yenisini ekle:"
HABIT_LIST_ITEM = "{status} {name}"
HABIT_LIST_ITEM_ACTIVE = "✅"
HABIT_LIST_ITEM_INACTIVE = "⬜"
HABIT_LIST_EMPTY = "Henüz rutin eklemedin. 🕐\n\n/rutin_ekle ile ilk rutinini oluştur."
HABIT_ASK_NAME = "Rutinin adı ne? (örn: Sabah sporu)\n\n/iptal ile vazgeçebilirsin."
HABIT_ASK_TIME = "Hangi saatte hatırlatayım? (örn: 08:30)\n\n/iptal ile vazgeçebilirsin."
HABIT_ASK_DAYS = (
    "Hangi günler geçerli olsun? (virgülle ayır, 1=Pazartesi ... 7=Pazar)\n\n"
    "Örn: 1,2,3,4,5 (hafta içi) ya da 1,2,3,4,5,6,7 (her gün)\n\n"
    "Boş bırakırsan her gün sayılır.\n\n/iptal ile vazgeçebilirsin."
)
HABIT_CONFIRM = "Rutin özeti 📝\n\nAd: {name}\nSaat: {time}\nGünler: {days}\n\nOnaylıyor musun?"
HABIT_CREATED = "Rutin oluşturuldu! ✅\n\n{rutin}"
HABIT_CANCELLED = "Rutin ekleme iptal edildi."
HABIT_DETAIL = (
    "Rutin: {name}\n\nSaat: {time}\nGünler: {days}\nDurum: {status}\n\nNe yapmak istersin?"
)
HABIT_STATUS_ACTIVE = "Aktif"
HABIT_STATUS_INACTIVE = "Kapalı"
HABIT_ACTIVATED = "Rutin açıldı. ✅"
HABIT_DEACTIVATED = "Rutin kapatıldı."
HABIT_INVALID_TIME = "Saat formatı geçersiz. HH:MM şeklinde yaz (örn: 08:30)."
HABIT_INVALID_DAYS = (
    "Gün formatı geçersiz. 1-7 arası sayılar kullan (örn: 1,3,5).\n\n"
    "Boş bırakırsan her gün sayılır."
)
HABIT_NOT_FOUND = "Rutin bulunamadı."
HABIT_DAYS_TR: dict[int, str] = {
    1: "Pzt",
    2: "Sal",
    3: "Çar",
    4: "Per",
    5: "Cum",
    6: "Cmt",
    7: "Paz",
}

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
    ("rutin", "Rutinlerini yönet"),
    ("rutin_ekle", "Yeni rutin ekle"),
    ("ayarlar", "Ayarları göster"),
    ("rapor", "Raporları göster"),
    ("yardim", "Yardım menüsü"),
]
