# RutinBot

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

### Komutlar

| Komut | Açıklama |
|---|---|
| `/start` | Ana menü |
| `/botlar` | Botları yönet (aç/kapat) |
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

## Yol Haritası

- **Faz 1**: FastAPI (mobil senkronizasyon), gerçek scheduler mantığı, raporlar, ayarlar
- **Faz 2**: Rutin (habit), Spor, Supplement botları
- **Faz 3**: Adım, Sağlık değerlendirme, İlaç botları

## Lisans

Özel proje — her hakkı saklıdır.
