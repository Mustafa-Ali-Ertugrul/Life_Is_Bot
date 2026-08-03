# Life Is Bot

Telegram tabanlı sağlık ve rutin takip botu. Günlük rutinler, spor, supplement, adım sayısı, sağlık değerlendirmesi ve ilaç takibi için modüler bir altyapı.

## Faz 0 (mevcut): Çekirdek Altyapı ve Ana Bot

- Telegram botu (polling) — `python-telegram-bot` v22
- Kullanıcı + Telegram hesabı eşleme
- Bot açma/kapama tercihleri (`bot_preferences`)
- Ortak hatırlatma event'leri (`reminder_events`)
- Ortak yanıt kayıtları (`user_responses`, `is_current` mantığı)
- Bildirim logları ve audit log
- APScheduler ile 1 dakikalık tick görevi (Faz 1'de gerçek hatırlatma mantığı)
- Global hata yakalayıcı (PII redaction ile)
- Kullanıcı onay akışı (`consent_given` / `consented_at`)
- Standart callback formatı: `ui:` (menü) ve `r:` (hatırlatma yanıtı) namespace'leri
- Sorgu index'leri (reminder_events, user_responses, notification_logs)
- GitHub Actions CI (mypy --strict, ruff, pytest)

## Faz 1: Hatırlatma Motoru ve Rutin Botu

- Gerçek hatırlatma motoru: due event tarama, atomik/idempotent `mark_notified`, duplicate önleme
- Bildirim mesajı + yanıt butonları (tamamlandı / yapılmadı / ertele / atla)
- Ertelenen (snooze) hatırlatma için yeni event üretimi
- Bot bazlı yanıt akışı ve `should_skip_notify` kontrolleri (tercih, yanıt, durum)
- Rutin (habit) botu: `/rutin` ve `/rutin_ekle` — isim, saat, gün seçimi (1-7)
- Günlük 00:05 job'ı ile habit'lere göre günlük hatırlatma event'leri üretimi
- `habits` tablosu + completion istatistikleri

### Komutlar

| Komut | Açıklama |
|---|---|
| `/start` | Ana menü |
| `/botlar` | Botları yönet (aç/kapat) |
| `/rutin` | Rutinlerini yönet |
| `/rutin_ekle` | Yeni rutin ekle (adım adım) |
| `/ayarlar` | Ayarlar (Faz 1) |
| `/rapor` | Raporlar (Faz 1) |
| `/yardim` | Yardım |

## Kurulum

```bash
# 1. Bağımlılıkları kur
uv sync

# 2. .env oluştur ve BOT_TOKEN doldur
cp .env.example .env

# 3. Veritabanı migration'larını uygula
uv run alembic upgrade head

# 4. Botu başlat
uv run python -m app.main
```

### Docker (production)

```bash
# 1. .env oluştur ve BOT_TOKEN doldur
cp .env.example .env

# 2. Image build et ve başlat (migrate + bot + api)
docker compose up -d --build

# 3. Logları gör
docker compose logs -f bot

# 4. Health check
curl http://localhost:8000/health
```

Üç servis: `migrate` (tek seferlik migration), `bot` (polling, varsayılan), `api` (REST + healthcheck). Veriler `./data/`, yedekler `./backups/`, raporlar `./reports/` dizinlerinde volume olarak saklanır.

#### GHCR'den (pre-built image)

`main` ve `v*` tag'lerinde image `ghcr.io/mustafa-ali-ertugrul/life_is_bot`'a yayınlanır. Local build yapmak yerine pre-built image kullanmak için `docker-compose.yml`'deki üç `image:` alanını güncelle:

```yaml
services:
  migrate:
    image: ghcr.io/mustafa-ali-ertugrul/life_is_bot:latest
    # build: .           # build satırını kaldır
  bot:
    image: ghcr.io/mustafa-ali-ertugrul/life_is_bot:latest
  api:
    image: ghcr.io/mustafa-ali-ertugrul/life_is_bot:latest
```

Sonra `--build` olmadan başlat:

```bash
docker compose up -d
docker compose ps -a                    # migrate Exited(0), api Up(healthy)
curl http://localhost:8000/health
```

Bu yol yine üç servisi (migrate + bot + api) çalıştırır; raw `docker run` image'i yalnızca polling bot'unu (`CMD ["python","-m","app.main"]`) başlatır, uvicorn/migration'ı içermez.

#### Webhook Mode (production, public URL gerekli)

```bash
# .env içinde:
# WEBHOOK_MODE=True
# TELEGRAM_WEBHOOK_URL=https://yourdomain.com/api/webhook/telegram
# TELEGRAM_WEBHOOK_SECRET=random_secret_here

# Telegram'a webhook bildir (bir kez):
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -d "url=https://yourdomain.com/api/webhook/telegram" \
  -d "secret_token=random_secret_here"

# Polling bot servisini durdur (webhook'u api servisi taşır):
docker compose stop bot
docker compose up -d --build
```

#### Yedekleme

Günlük yedekler `./backups/` dizininde. Manuel yedekleme:

```bash
cp ./data/life_is_bot.db ./data/life_is_bot_$(date +%Y-%m-%d).db
```

#### Veri Temizleme

`PURGE_ENABLED=True` ile ayın son günü aylık rapordan sonra (23:55) eski veriler silinir ve `VACUUM` çalışır. `DATA_RETENTION_MONTHS` (varsayılan 1) geçerli ay dahil tutulacak geçmiş ay sayısıdır; silinenler: eski `reminder_events`, `user_responses`, `notification_logs`, `step_logs`, `audit_logs`. Aktif planlar, kullanıcılar ve onboarding yanıtları korunur.

#### Güncelleme

```bash
git pull
docker compose up -d --build
```

#### Smoke Test

```bash
./scripts/smoke_test.sh
```

## Geliştirme

```bash
uv run mypy app/ --strict
uv run ruff check app/
uv run ruff format --check app/
uv run pytest tests/ -v
```

## Veritabanı Şeması

| Tablo | Açıklama |
|---|---|
| `users` | Kullanıcılar, zaman dilimi, onay |
| `telegram_accounts` | Telegram hesap eşlemesi |
| `bot_preferences` | Bot bazlı aç/kapat tercihleri |
| `reminder_events` | Hatırlatma event'leri |
| `user_responses` | Kullanıcı yanıtları (audit: `is_current`) |
| `notification_logs` | Gönderilen bildirim logları |
| `audit_logs` | Denetim logları |
| `habits` | Rutin (habit) tanımları |

## Yol Haritası

- **Faz 1**: ✅ Hatırlatma motoru, Rutin botu
- **Faz 1.5**: ✅ Data integrity (dedupe, check constraints, migration dizisi) + Quiet hours enforcement (notification policy, `SUPPRESSED` durumu, erteleme)
- **Faz 2**: Spor, Supplement botları (öncesi: services audit, BotModule interface)
- **Faz 3**: Adım, Sağlık değerlendirme, İlaç botları

### Backlog

- Notification retry (başarısız Telegram gönderimi, backoff)
- DST/timezone geçiş testleri (quiet hours)
- Aylık rapor
- Notification channel abstraction (Telegram → mobil push)

## Lisans

Özel proje — her hakkı saklıdır.
