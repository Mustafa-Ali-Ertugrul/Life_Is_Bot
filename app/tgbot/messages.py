from app.models import BotKey

WELCOME = (
    "Merhaba 👋\n\n"
    "Ben Life Is Bot.\n\n"
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
    "Onay verilmediği için Life Is Bot kullanılamıyor. "
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
    "Life Is Bot yardım 📖\n\n"
    "/start - Ana menüyü aç\n"
    "/botlar - Botları yönet\n"
    "/rutin - Rutinlerini yönet\n"
    "/rutin_ekle - Yeni rutin ekle\n"
    "/spor - Spor menüsünü aç\n"
    "/spor_ekle - Yeni spor planı ekle\n"
    "/spor_listesi - Spor planlarını listele\n"
    "/adim - Adım takibi menüsünü aç\n"
    "/adim_gir - Bugünkü adımını gir\n"
    "/ilac - İlaç takibi menüsünü aç\n"
    "/ayarlar - Ayarları göster\n"
    "/rapor - Raporları göster\n"
    "/aylik_rapor - Aylık rapor göster\n"
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
    "Yeni timezone'u IANA adıyla yaz (örn: Europe/Istanbul).\n\n/iptal ile vazgeçebilirsin."
)
SETTINGS_INVALID_TIMEZONE = "Geçersiz timezone. IANA adı kullan (örn: Europe/Istanbul)."
SETTINGS_TIMEZONE_UPDATED = "Timezone güncellendi: {timezone} ✅"
SETTINGS_ASK_QUIET_START = (
    "Sessiz saatlerin başlangıcı (HH:MM, örn: 23:00)?\n\n/iptal ile vazgeçebilirsin."
)
SETTINGS_ASK_QUIET_END = (
    "Sessiz saatlerin bitişi (HH:MM, örn: 07:00)?\n\n/iptal ile vazgeçebilirsin."
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
DAILY_REPORT_STEP_LINE = "🚶 Adım: {steps} / {goal} ({pct}%)"
REPORT_COMPLIANCE = "Uyum oranı: %{rate}"
REPORT_BEST_DAY = "En iyi gün: {day}"
REPORT_WEAKEST_DAY = "En zayıf gün: {day}"

MONTHLY_REPORT_HEADER = "📊 Aylık Rapor — {month_label}"
MONTHLY_REPORT_EMPTY = "📊 {month_label}\n\nBu ay için henüz veri yok."
MONTHLY_REPORT_OVERALL = "🎯 Genel Tamamlama: %{rate} ({completed}/{total})"
MONTHLY_REPORT_BOT_LINE = "{icon} {name}: %{rate} ({completed}/{total})"
MONTHLY_REPORT_LEGEND = (
    "✅ Tamamlanan: {completed} | ❌ Kaçırılan: {missed} | ⏳ Bekleyen: {pending}"
)
MONTHLY_REPORT_INVALID_ARG = "❌ Geçersiz format. Kullanım: /aylik_rapor veya /aylik_rapor 2026-08"

MONTHS_TR = [
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
]

BOT_ICONS: dict[BotKey, str] = {
    BotKey.CORE: "📌",
    BotKey.HABIT: "🔁",
    BotKey.SPORT: "🏃",
    BotKey.SUPPLEMENT: "💊",
    BotKey.STEP: "🚶",
    BotKey.ASSESSMENT: "🩺",
    BotKey.MEDICATION: "💊",
}

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

SPORT_MENU = "Spor menüsü 🏋️\n\nNe yapmak istersin?"
SPORT_LIST_HEADER = "Spor planların:\n\n{BOT_LIST}\n\nBir plan seç veya yenisini ekle:"
SPORT_LIST_ITEM = "{status} {sport_type}"
SPORT_LIST_ITEM_ACTIVE = "✅"
SPORT_LIST_ITEM_INACTIVE = "⬜"
SPORT_LIST_EMPTY = "Henüz spor planın yok. 🕐\n\n/spor_ekle ile ilk planını oluştur."
SPORT_ASK_TYPE = (
    "Spor türünü yaz.\n\nÖrnek: Fitness, Koşu, Yüzme, Yoga\n\n/iptal ile vazgeçebilirsin."
)
SPORT_ASK_DAYS = (
    "Hangi günler yapacaksın? (gün adları veya sayılar)\n\n"
    "Örn: Pazartesi, Çarşamba, Cuma ya da 1,3,5\n\n"
    "Boş bırakırsan hafta içi sayılır.\n\n/iptal ile vazgeçebilirsin."
)
SPORT_ASK_TIME = (
    "Hangi saatte hatırlatayım? (örn: 19:00, 19.00, 1900)\n\n/iptal ile vazgeçebilirsin."
)
SPORT_CONFIRM = "Plan eklensin mi?"
SPORT_CREATED = "Spor planın eklendi. ✅"
SPORT_CANCELLED = "Spor planı ekleme iptal edildi."
SPORT_DETAIL = (
    "Spor: {sport_type}\n\nSaat: {time}\nGünler: {days}\nDurum: {status}\n\nNe yapmak istersin?"
)
SPORT_STATUS_ACTIVE = "Aktif"
SPORT_STATUS_INACTIVE = "Kapalı"
SPORT_TOGGLED_ON = "Spor planı aktif edildi. ✅"
SPORT_TOGGLED_OFF = "Spor planı kapatıldı."
SPORT_INVALID_TYPE = "Spor türü boş olamaz. Tekrar yaz."
SPORT_INVALID_TIME = "Saat formatı geçersiz. 19:00, 19.00 veya 1900 şeklinde yaz."
SPORT_INVALID_DAYS = (
    "Gün formatı geçersiz. Gün adı veya 1-7 arası sayı yaz (örn: 1,3,5).\n\n"
    "Boş bırakırsan hafta içi sayılır."
)
SPORT_NOT_FOUND = "Spor planı bulunamadı."
SPORT_DAYS_TR: dict[int, str] = HABIT_DAYS_TR

SUPPLEMENT_MENU = (
    "Supplement botu\n\nSupplement planlarını buradan yönetebilirsin.\n\nNe yapmak istersin?"
)
SUPPLEMENT_LIST_HEADER = "Supplement planların:\n\n{BOT_LIST}\n\nBir plan seç veya yenisini ekle:"
SUPPLEMENT_LIST_ITEM = "{status} {name}"
SUPPLEMENT_LIST_ITEM_ACTIVE = "✅"
SUPPLEMENT_LIST_ITEM_INACTIVE = "⬜"
SUPPLEMENT_LIST_EMPTY = (
    "Henüz supplement planın yok.\n\n"
    "Yeni plan eklemek için /supplement_ekle komutunu kullanabilirsin."
)
SUPPLEMENT_ASK_NAME = "Supplement adını yaz.\n\nÖrnek:\nOmega-3\nVitamin D\nMagnesium"
SUPPLEMENT_ASK_DOSE = (
    'Doz bilgisini yaz.\n\nÖrnek:\n1 kapsül\n1 damla\n5 mg\n\nDoz belirtmek istemiyorsan "yok" yaz.'
)
SUPPLEMENT_ASK_WITH_FOOD = "Nasıl kullanacaksın?\n\nAç karnına\nTok karnına\nFark etmez"
SUPPLEMENT_ASK_DAYS = "Hangi günler?\n\nÖrnek:\nHer gün\nPazartesi, Çarşamba, Cuma\n1,3,5"
SUPPLEMENT_ASK_TIME = "Saat kaçta?\n\nÖrnek:\n09:00\n21:30"
SUPPLEMENT_ASK_DURATION = (
    "Bu supplement kaç gün sürecek?\n\nSüresiz ise 0 yaz.\n\nÖrnek:\n0\n14\n30"
)
SUPPLEMENT_CONFIRM = "Supplement planı eklensin mi?"
SUPPLEMENT_CREATED = "Supplement planın eklendi. ✅"
SUPPLEMENT_CANCELLED = "Supplement planı ekleme iptal edildi."
SUPPLEMENT_INVALID_NAME = "Geçersiz supplement adı. Lütfen bir isim yaz."
SUPPLEMENT_INVALID_WITH_FOOD = (
    "Kullanım şeklini anlayamadım.\n\n"
    "Lütfen şunlardan birini yaz:\n"
    "Aç karnına\n"
    "Tok karnına\n"
    "Fark etmez"
)
SUPPLEMENT_INVALID_DAYS = "Günleri anlayamadım. Örnek: Her gün veya Pazartesi, Çarşamba, Cuma"
SUPPLEMENT_INVALID_TIME = "Saati anlayamadım. Örnek: 09:00"
SUPPLEMENT_INVALID_DURATION = "Süreyi anlayamadım. Örnek: 0, 14, 30"
SUPPLEMENT_DETAIL = (
    "Supplement planı\n\n"
    "Ad: {name}\n"
    "Doz: {dose}\n"
    "Kullanım: {with_food}\n"
    "Günler: {days}\n"
    "Saat: {time}\n"
    "Süre: {duration}\n"
    "Durum: {status}"
)
SUPPLEMENT_STATUS_ACTIVE = "Aktif"
SUPPLEMENT_STATUS_INACTIVE = "Kapalı"
SUPPLEMENT_TOGGLED_ON = "Supplement planı aktif edildi. ✅"
SUPPLEMENT_TOGGLED_OFF = "Supplement planı pasif edildi."
SUPPLEMENT_NOT_FOUND = "Supplement planı bulunamadı."
SUPPLEMENT_DAYS_TR: dict[int, str] = HABIT_DAYS_TR

STEP_MENU_HEADER = "🚶 Adım Takibi"
STEP_TODAY_PROGRESS = "📊 Bugün: {steps} / {goal} adım ({pct}%)"
STEP_TODAY_EMPTY = "📊 Bugün: Henüz adım girilmedi"
STEP_GOAL_LINE = "🎯 Hedef: {goal} adım"
STEP_REMINDER_LINE = "⏰ Hatırlatma: {time}"
STEP_DAYS_LINE = "📅 Günler: {days}"
STEP_STATUS_ACTIVE = "✅ Aktif"
STEP_STATUS_INACTIVE = "⏸️ Pasif"

STEP_SETTINGS_HEADER = "⚙️ Adım Ayarları"
STEP_SETTINGS_GOAL = "🎯 Günlük Hedef: {goal}"
STEP_SETTINGS_TIME = "⏰ Hatırlatma Saati: {time}"
STEP_SETTINGS_DAYS = "📅 Günler: {days}"
STEP_SETTINGS_STATUS = "📊 Durum: {status}"

STEP_LOG_PROMPT = "📝 Bugünkü adım sayını gir:\nÖrn: 7500\n\n/iptal ile vazgeçebilirsin."
STEP_LOG_SAVED = "✅ {steps} adım kaydedildi!\n🎯 Hedef: {goal} adım ({pct}%)"
STEP_LOG_UPDATED = "🔄 Adım güncellendi: {steps} adım\n🎯 Hedef: {goal} adım ({pct}%)"
STEP_INVALID_STEPS = "❌ Geçersiz adım sayısı. Lütfen 0-200000 arası bir sayı gir."

STEP_GOAL_PROMPT = "🎯 Yeni günlük adım hedefini gir:\nÖrn: 10000\n\n/iptal ile vazgeçebilirsin."
STEP_GOAL_SAVED = "✅ Günlük hedef {goal} adım olarak güncellendi."
STEP_INVALID_GOAL = "❌ Geçersiz hedef. Lütfen 0-100000 arası bir sayı gir."

STEP_TIME_PROMPT = "⏰ Yeni hatırlatma saatini gir:\nÖrn: 21:00\n\n/iptal ile vazgeçebilirsin."
STEP_TIME_SAVED = "✅ Hatırlatma saati {time} olarak güncellendi."
STEP_INVALID_TIME = "❌ Geçersiz saat formatı. Lütfen HH:MM formatında gir (örn: 21:00)."

STEP_DAYS_PROMPT = (
    "📅 Hatırlatma günlerini gir:\nÖrn: pzt, sal, çar, per, cum veya her gün\n\n"
    "/iptal ile vazgeçebilirsin."
)
STEP_DAYS_SAVED = "✅ Günler güncellendi: {days}"
STEP_INVALID_DAYS = (
    "❌ Geçersiz gün listesi. Lütfen gün adlarını virgülle ayır (örn: pzt, çar, cum)."
)

STEP_TOGGLED_ON = "▶️ Adım takibi aktif edildi."
STEP_TOGGLED_OFF = "⏸️ Adım takibi pasif edildi."
STEP_CANCELLED = "❌ İşlem iptal edildi."
STEP_FIRST_ACTIVATION = "🚶 Adım takibi aktif edildi! /adim ile menüye ulaşabilirsin."

MED_MENU = "İlaç botu\n\nİlaç planlarını buradan yönetebilirsin.\n\nNe yapmak istersin?"
MED_LIST_HEADER = "İlaç planların:\n\n{BOT_LIST}\n\nBir plan seç veya yenisini ekle:"
MED_LIST_ITEM = "{status} {name}"
MED_LIST_ITEM_ACTIVE = "✅"
MED_LIST_ITEM_INACTIVE = "⬜"
MED_LIST_EMPTY = (
    "Henüz ilaç planın yok.\n\nYeni plan eklemek için /ilac_ekle komutunu kullanabilirsin."
)
MED_ASK_NAME = "İlaç adını yaz.\n\nÖrnek:\nMetformin\nVitamin D\nTansiyon ilacı"
MED_ASK_DOSE = (
    "Doz bilgisini yaz.\n\nÖrnek:\n1 tablet\n500 mg\n1 ölçek\n\n"
    'Doz belirtmek istemiyorsan "yok" yaz.'
)
MED_ASK_WITH_FOOD = "Nasıl kullanacaksın?\n\nAç karnına\nTok karnına\nFark etmez"
MED_ASK_DAYS = "Hangi günler?\n\nÖrnek:\nHer gün\nPazartesi, Çarşamba, Cuma\n1,3,5"
MED_ASK_TIME = "Saat kaçta?\n\nÖrnek:\n08:00\n21:30"
MED_ASK_DURATION = "Bu ilaç kaç gün sürecek?\n\nSüresiz ise 0 yaz.\n\nÖrnek:\n0\n14\n30"
MED_ASK_NOTES = (
    'Ek not var mı? (opsiyonel)\n\nÖrnek:\nAç karnına, bol su ile\n\nNot yoksa "yok" yaz.'
)
MED_CONFIRM = "İlaç planı eklensin mi?"
MED_CREATED = "İlaç planın eklendi. ✅"
MED_CANCELLED = "İlaç planı ekleme iptal edildi."
MED_INVALID_NAME = "Geçersiz ilaç adı. Lütfen bir isim yaz."
MED_INVALID_WITH_FOOD = (
    "Kullanım şeklini anlayamadım.\n\n"
    "Lütfen şunlardan birini yaz:\n"
    "Aç karnına\n"
    "Tok karnına\n"
    "Fark etmez"
)
MED_INVALID_DAYS = "Günleri anlayamadım. Örnek: Her gün veya Pazartesi, Çarşamba, Cuma"
MED_INVALID_TIME = "Saati anlayamadım. Örnek: 08:00"
MED_INVALID_DURATION = "Süreyi anlayamadım. Örnek: 0, 14, 30"
MED_DETAIL = (
    "İlaç planı\n\n"
    "Ad: {name}\n"
    "Doz: {dose}\n"
    "Kullanım: {with_food}\n"
    "Günler: {days}\n"
    "Saat: {time}\n"
    "Süre: {duration}\n"
    "Not: {notes}\n"
    "Durum: {status}"
)
MED_STATUS_ACTIVE = "Aktif"
MED_STATUS_INACTIVE = "Kapalı"
MED_TOGGLED_ON = "İlaç planı aktif edildi. ✅"
MED_TOGGLED_OFF = "İlaç planı pasif edildi."
MED_NOT_FOUND = "İlaç planı bulunamadı."
MED_DAYS_TR: dict[int, str] = HABIT_DAYS_TR

BOT_KEYS_TR: dict[BotKey, str] = {
    BotKey.CORE: "Genel Rutin",
    BotKey.HABIT: "Rutin",
    BotKey.SPORT: "Spor",
    BotKey.SUPPLEMENT: "Supplement",
    BotKey.STEP: "Adım",
    BotKey.ASSESSMENT: "Sağlık",
    BotKey.MEDICATION: "İlaç",
}

ABANDONED_SINGLE = (
    "⚠️ {bot_name} hatırlatmanız gönderilemedi.\n\n"
    "Birden fazla deneme başarısız oldu. "
    "Bağlantınızı kontrol edin veya botu yeniden başlatın."
)
ABANDONED_MULTIPLE = (
    "⚠️ {count} hatırlatma gönderilemedi.\n\n"
    "Etkilenen botlar: {bot_names}\n"
    "Bağlantınızı kontrol edin veya botu yeniden başlatın."
)

DIGEST_HEADER = "📋 Son hatırlatmalarınız\n\n"
DIGEST_ITEM = "• {bot_name}: {label}"

COMMANDS = [
    ("start", "Ana menüyü aç"),
    ("botlar", "Botları yönet"),
    ("rutin", "Rutinlerini yönet"),
    ("rutin_ekle", "Yeni rutin ekle"),
    ("spor", "Spor menüsünü aç"),
    ("spor_ekle", "Yeni spor planı ekle"),
    ("spor_listesi", "Spor planlarını listele"),
    ("supplement", "Supplement menüsünü aç"),
    ("supplement_ekle", "Yeni supplement planı ekle"),
    ("supplement_listesi", "Supplement planlarını listele"),
    ("adim", "Adım takibi menüsü"),
    ("adim_gir", "Bugünkü adımını gir"),
    ("ilac", "İlaç takibi menüsünü aç"),
    ("ilac_ekle", "Yeni ilaç planı ekle"),
    ("ilac_listesi", "İlaç planlarını listele"),
    ("ayarlar", "Ayarları göster"),
    ("rapor", "Raporları göster"),
    ("aylik_rapor", "Aylık rapor göster"),
    ("yardim", "Yardım menüsü"),
]
