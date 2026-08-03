from app.services.streak_service import StreakReport
from app.tgbot.report_handlers import _format_streak


def test_format_streak_empty() -> None:
    report = StreakReport(user_id=1, current=0, longest=0, today_completed=False)

    text = _format_streak(report)

    assert "Henüz tamamlanmış hatırlatma yok" in text


def test_format_streak_today_pending() -> None:
    report = StreakReport(user_id=1, current=2, longest=5, today_completed=False)

    text = _format_streak(report)

    assert "Seri: 2 gün" in text
    assert "En uzun seri: 5 gün" in text
    assert "Bugün henüz tamamlanmadı" in text


def test_format_streak_today_completed() -> None:
    report = StreakReport(user_id=1, current=3, longest=3, today_completed=True)

    text = _format_streak(report)

    assert "Seri: 3 gün" in text
    assert "En uzun seri: 3 gün" in text
    assert "Bugün tamamlandı ✅" in text
