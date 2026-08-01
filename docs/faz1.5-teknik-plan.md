# Faz 1.5 Teknik Plan — Stabilizasyon ve Kullanıcı Görünürlüğü

Hedef: Merge edilen Faz 1 çekirdeğini (v0.1.0-faz1) küçük, sınırlı değişikliklerle sağlamlaştırmak
ve kullanıcıya "bugün ne yaptım / bu hafta nasıl gidiyorum" görünürlüğü kazandırmak.
FastAPI mobil senkronizasyon için yalnızca minimal iskelet (health + auth) — kapsam genişletilmez.

## Kapsam

1. Günlük rapor
2. Haftalık rapor
3. `/rapor` komutu
4. `/ayarlar` komutu
5. Timezone ayarı
6. Bildirim tercihi (mevcut `bot_preferences` üzerinden)
7. Quiet hours (sessiz saatler)
8. Minimal FastAPI: `/healthz` + auth iskeleti

## Mimari Kararlar

- **Raporlar salt-okunur servis**: `app/services/report_service.py` — `reminder_events` +
  `user_responses` (is_current=True) üzerinden istatistik; yeni tablo yok.
- **Ayarlar kullanıcı bazlı**: `User.timezone` mevcut; `quiet_hours` için `User`'a iki alan
  (`quiet_start_hour`, `quiet_end_hour`) veya ayrı `user_settings` tablosu. Tercih: `User`
  üzerine alanlar (tek tablo, basit migration) — YAGNI.
- **Zaman dilimi**: `now_in(user_timezone)` helper'ı günlük event üretiminde ve rapor
  pencerelerinde kullanılır. `habit_daily` job'ı kullanıcı bazlı timezone ile üretim yapar
  (job saati server timezone'unda kalır; pencere hesabı kullanıcı diliminde).
- **Quiet hours**: `reminder_tick` içinde saat penceresi kontrolü — `should_skip_notify`
  zincirine eklenir; atlanan event'ler NOTIFIED yapılmaz, sonraki tick'te denenir.
- **API iskeleti**: `app/api/` — FastAPI + uvicorn; `/healthz` DB `SELECT 1` döner;
  auth skeleton olarak `X-API-Key` header karşılaştırması (`settings.api_key`).
- **BotModule soyutlaması Faz 1.5'e dahil değil** — Faz 2 başlangıcında Spor botuyla birlikte
  değerlendirilir.

## İş Parçaları (sıralı PR'lar)

### PR 1.5.1 — Raporlar
- `report_service.py`:
  - `daily_report(session, user_id, day) -> dict`:
    - `total`, `completed`, `missed`, `unanswered`
    - Tamamlananlar (✅) ve kaçırılanlar (❌) listesi (habit adı etiketiyle)
  - `weekly_report(session, user_id, week_start) -> dict`:
    - `total`, `completed`, `missed`, `unanswered`, `compliance_rate`
    - `best_day`, `weakest_day` (yanıt oranına göre)
- `/rapor` komutu: günlük raporu gösterir; inline "Haftalık" butonu (ui namespace)
- `ui:reports` callback'i gerçek içerikle doldurulur (REPORT_STUB kaldırılır)
- Testler: `tests/test_report_service.py` (7 günlük veri, boş veri, kısmi yanıt)

### PR 1.5.2 — Ayarlar
- `/ayarlar` komutu: mevcut ayarları gösterir (timezone, bildirimler, quiet hours, dil)
- Timezone değiştirme: `ui:settings:timezone` → ConversationHandler (IANA bölge girişi) veya
  kısa liste; `User.timezone` güncellenir
- Bildirim toggle: global `bot_preferences` (CORE hariç hepsi) veya tek bot bazlı — mevcut
  `_toggle_bot` akışı yeniden kullanılır
- Quiet hours: `ui:settings:quiet` → başlangıç/bitiş girişi (HH:MM)
- `ui:settings` callback'i gerçek içerikle doldurulur (SETTINGS_STUB kaldırılır)
- Migration: `users` tablosuna `quiet_start_hour`, `quiet_end_hour` (nullable Integer)
- Testler: `tests/test_settings.py`

### PR 1.5.3 — Quiet hours entegrasyonu + zaman dilimi
- `should_skip_notify`'a quiet hours kontrolü (kullanıcının local saatine göre)
- `habit_service.generate_today_events`: kullanıcının timezone'unda "bugün" hesabı
- `reminder_service.find_due_events`: kullanıcı bazlı local saat sınırı (opsiyonel — pencere
  hesaplarında)
- Testler: timezone farklı kullanıcı senaryosu, quiet hours penceresi

### PR 1.5.4 — Minimal FastAPI
- `app/api/main.py` — `create_app()`: `/healthz` (DB check), `/api/v1/health` alias
- `app/main.py`'ye opsiyonel API başlatma: `RUN_API=true` olduğunda uvicorn ile birlikte
  (ayrı process önerilir — bot polling ile aynı event loop'ta çalıştırma riski)
- `X-API-Key` auth skeleton: `app/api/auth.py` dependency
- Testler: `tests/test_api.py` (healthz 200, auth 401/403)

## Kullanıcı Görünürlüğü Örnekleri

### Günlük rapor
```
Bugünkü özet:

Toplam rutin: 3
Tamamlanan: 2
Kaçırılan: 1
Yanıt verilmeyen: 0

Tamamlananlar:
✅ Su iç
✅ Diş fırçala

Kaçırılanlar:
❌ Kitap oku
```

### Haftalık rapor
```
Bu hafta:

Toplam: 21
Tamamlanan: 17
Kaçırılan: 3
Yanıtsız: 1

Uyum oranı: %81

En iyi gün: Pazartesi
En zayıf gün: Cuma
```

### Ayarlar menüsü
```
Ayarlar:

Timezone: Europe/Istanbul
Bildirimler: Açık
Sessiz saatler: 23:00 - 07:00
Dil: Türkçe

[Timezone Değiştir]
[Bildirimleri Kapat/Aç]
[Sessiz Saatler]
[Geri]
```

## Migration Zinciri (mevcut + yeni)

```
10abec0d171f (Faz 0 initial)
  ↓
a1b2c3d4e5f6 (consent)
  ↓
f1e2d3c4b5a6 (indexes)
  ↓
b5a6c7d8e9f0 (habits)   ← şu anki head
  ↓
[1.5.2] users quiet hours alanları (yeni revision)
```

## Kalite Kapıları (her PR için)

```bash
uv run mypy app/ tests/ --strict
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/
uv run pytest tests/ -v
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

## Açık Issue'lar (GitHub)

- P0 #5: unique constraint (reminder event idempotency — DB seviyesi)
- P0 #6: manuel event üretim komutu (`/rutin_urete` admin allowlist)
- P0 #7: notification failure logging (`status="failed"` + retry politikası)
- P0 #8: smoke test scripti (`scripts/smoke_test.py`)
- P1 (Faz 1.5 kapsamında açılacak): user-local timezone issue, conversation state
  persistence, HMAC callback imzalama (webhook öncesi), notification retry/backoff,
  rate limiting, veri ihracı/silme, PII redaction iyileştirmeleri

## Faz 2 Ön Hazırlık (bu fazda YAPILMAZ)

- BotModule interface tasarımı (bot_key, commands, callbacks, due generator, message
  builder, response processor, report contributor)
- Spor Botu ve Supplement Botu, Faz 1.5 PR'ları merge edildikten sonra ayrı plan ile başlar
