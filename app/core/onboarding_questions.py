"""Onboarding question definitions — static, no DB table needed."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class QuestionType(StrEnum):
    YES_NO = "yes_no"
    SINGLE_CHOICE = "single"
    MULTI_CHOICE = "multi"
    NUMBER_INPUT = "number"


@dataclass(frozen=True)
class OnboardingQuestion:
    key: str
    text: str
    question_type: QuestionType
    options: list[str]
    category: str
    condition: Callable[[dict[str, str]], bool] | None = None


ONBOARDING_QUESTIONS: list[OnboardingQuestion] = [
    # ── A: Temel Bilgiler ──
    OnboardingQuestion(
        "a1_gender",
        "Cinsiyetiniz?",
        QuestionType.SINGLE_CHOICE,
        ["Kadın", "Erkek", "Diğer", "Belirtmek istemiyorum"],
        "basic",
    ),
    OnboardingQuestion(
        "a2_age",
        "Yaş aralığınız?",
        QuestionType.SINGLE_CHOICE,
        ["18-25", "26-35", "36-50", "51+"],
        "basic",
    ),
    OnboardingQuestion(
        "a3_height",
        "Boyunuz?",
        QuestionType.SINGLE_CHOICE,
        ["<160 cm", "160-175 cm", "176-190 cm", ">190 cm"],
        "basic",
    ),
    OnboardingQuestion(
        "a4_weight",
        "Kilonuz?",
        QuestionType.SINGLE_CHOICE,
        ["<60 kg", "60-80 kg", "81-100 kg", ">100 kg"],
        "basic",
    ),
    OnboardingQuestion(
        "a5_work",
        "Çalışma durumunuz?",
        QuestionType.SINGLE_CHOICE,
        ["Masa başı", "Ayakta", "Fiziksel iş", "Karışık"],
        "basic",
    ),
    # ── B: Sağlık ──
    OnboardingQuestion(
        "b1_chronic",
        "Kalıcı (kronik) bir hastalığınız var mı?",
        QuestionType.YES_NO,
        ["Evet", "Hayır"],
        "health",
    ),
    OnboardingQuestion(
        "b2_medication",
        "Düzenli ilaç kullanıyor musunuz?",
        QuestionType.YES_NO,
        ["Evet", "Hayır"],
        "health",
    ),
    OnboardingQuestion(
        "b3_doctor",
        "Düzenli doktor kontrolüne gidiyor musunuz?",
        QuestionType.YES_NO,
        ["Evet", "Hayır"],
        "health",
    ),
    OnboardingQuestion(
        "b4_sleep",
        "Uyku düzeniniz nasıl?",
        QuestionType.SINGLE_CHOICE,
        ["Düzenli", "Düzensiz", "Değişken"],
        "health",
    ),
    OnboardingQuestion(
        "b5_stress",
        "Günlük stres seviyeniz?",
        QuestionType.SINGLE_CHOICE,
        ["Düşük", "Orta", "Yüksek", "Çok yüksek"],
        "health",
    ),
    # ── C: Spor & Aktivite ──
    OnboardingQuestion(
        "c1_sport_freq",
        "Düzenli spor yapıyor musunuz?",
        QuestionType.SINGLE_CHOICE,
        ["Haftada 3+", "Haftada 1-2", "Nadiren", "Hayır"],
        "sport",
    ),
    OnboardingQuestion(
        "c2_sport_type",
        "Ne tür aktivite?",
        QuestionType.SINGLE_CHOICE,
        ["Koşu-Yürüyüş", "Salon-Ağırlık", "Yüzme-Bisiklet", "Yapmıyorum"],
        "sport",
    ),
    OnboardingQuestion(
        "c3_steps_avg",
        "Günlük ortalama adım sayınız?",
        QuestionType.SINGLE_CHOICE,
        ["<3.000", "3.000-7.000", "7.000-10.000", ">10.000"],
        "sport",
    ),
    OnboardingQuestion(
        "c4_wants_steps",
        "Adım hedefi belirlemek ister misiniz?",
        QuestionType.YES_NO,
        ["Evet", "Hayır"],
        "sport",
    ),
    OnboardingQuestion(
        "c4a_step_goal",
        "🚶 Günlük adım hedefiniz kaç olsun?\n"
        "Butondan seçebilir veya sayı yazabilirsiniz (örn: 8000)",
        QuestionType.NUMBER_INPUT,
        [],
        "sport",
        condition=lambda a: a.get("c4_wants_steps") == "Evet",
    ),
    # ── D: Beslenme & Takviye ──
    OnboardingQuestion(
        "d1_supplements",
        "Takviye (vitamin/supplement) kullanıyor musunuz?",
        QuestionType.YES_NO,
        ["Evet", "Hayır"],
        "nutrition",
    ),
    OnboardingQuestion(
        "d2_nutrition",
        "Beslenme düzeniniz nasıl?",
        QuestionType.SINGLE_CHOICE,
        ["Düzenli", "Düzensiz", "Diyet programı", "Karışık"],
        "nutrition",
    ),
    OnboardingQuestion(
        "d3_water",
        "Günlük su tüketiminiz?",
        QuestionType.SINGLE_CHOICE,
        ["<1 litre", "1-2 litre", "2-3 litre", ">3 litre"],
        "nutrition",
    ),
    # ── E: Hedefler ──
    OnboardingQuestion(
        "e1_goals",
        "Bu botu ne için kullanacaksınız?\n(Birden fazla seçebilirsiniz)",
        QuestionType.MULTI_CHOICE,
        ["Rutin takibi", "Sağlık-İlaç", "Spor", "Adım", "Beslenme"],
        "goals",
    ),
    OnboardingQuestion(
        "e2_reminder_freq",
        "Hatırlatma sıklığı tercihiniz?",
        QuestionType.SINGLE_CHOICE,
        ["Sık", "Günde 1-2", "Sadece önemli", "Minimum"],
        "goals",
    ),
]


def get_next_question(
    current_index: int, answers: dict[str, str]
) -> tuple[int, OnboardingQuestion] | None:
    """Sonraki görünür soruyu bul. Koşulu sağlamayanları atla."""
    for i in range(current_index + 1, len(ONBOARDING_QUESTIONS)):
        q = ONBOARDING_QUESTIONS[i]
        if q.condition is None or q.condition(answers):
            return i, q
    return None


__all__ = [
    "ONBOARDING_QUESTIONS",
    "OnboardingQuestion",
    "QuestionType",
    "get_next_question",
]
