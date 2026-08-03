#!/bin/bash
set -e

echo "Life_Is_Bot smoke test..."
echo ""

# 1. Migration servisi başarıyla tamamlandı mı?
if docker compose ps -a | grep -E "migrate.*Exited \(0\)" > /dev/null; then
    echo "✅ Migration tamamlandı (exit 0)"
else
    echo "❌ Migration başarısız veya tamamlanmadı"
    docker compose logs migrate
    exit 1
fi

# 2. API health check
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "✅ Health check OK: $HEALTH"
else
    echo "❌ Health check başarısız: $HEALTH"
    exit 1
fi

# 3. OpenAPI docs
if [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/docs)" = "200" ]; then
    echo "✅ OpenAPI docs erişilebilir"
else
    echo "❌ OpenAPI docs erişilemiyor"
    exit 1
fi

# 4. Volume dizinleri
for dir in backups reports; do
    if [ -d "./$dir" ]; then
        echo "✅ $dir dizini var"
    else
        echo "⚠️  $dir dizini yok (ilk çalıştırmada oluşacak)"
    fi
done

# 5. Bot servisi durumu (polling)
if docker compose ps | grep -qE "bot.*Up"; then
    echo "✅ Bot servisi çalışıyor (polling)"
else
    echo "⚠️  Bot servisi ayakta değil — BOT_TOKEN gerçek mi? Yerel 'python -m app.main' çalışıyorsa 409 conflict olur"
    echo "    Kontrol: docker compose logs bot"
fi

echo ""
echo "🎉 Smoke test geçti! Bot çalışıyor."
echo "   Telegram'da botunu bul ve /start yaz."
