"""Onboarding service: save answers, compute profile, apply preferences."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.onboarding_questions import ONBOARDING_QUESTIONS
from app.core.timezone import now_in
from app.models import BotKey, OnboardingAnswer, User
from app.services import preference_service, step_service

PROFILE_CHRONIC = "chronic"
PROFILE_ATHLETE = "athlete"
PROFILE_MIXED = "mixed"
PROFILE_GENERAL = "general"


async def save_answer(
    session: AsyncSession, user_id: int, question_key: str, answer_value: str
) -> OnboardingAnswer:
    """Upsert: aynı soru tekrar cevaplanırsa güncelle."""
    stmt = select(OnboardingAnswer).where(
        OnboardingAnswer.user_id == user_id,
        OnboardingAnswer.question_key == question_key,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.answer_value = answer_value
        await session.flush()
        return existing

    answer = OnboardingAnswer(user_id=user_id, question_key=question_key, answer_value=answer_value)
    session.add(answer)
    await session.flush()
    return answer


async def get_answers(session: AsyncSession, user_id: int) -> dict[str, str]:
    """Kullanıcının tüm cevaplarını dict olarak döndür."""
    stmt = select(OnboardingAnswer).where(OnboardingAnswer.user_id == user_id)
    result = await session.execute(stmt)
    return {a.question_key: a.answer_value for a in result.scalars().all()}


def compute_flags(answers: dict[str, str]) -> dict[str, bool]:
    """Cevaplardan profil flag'lerini çıkar."""
    goals = answers.get("e1_goals", "")
    return {
        "has_chronic": (
            answers.get("b1_chronic") == "Evet" or answers.get("b2_medication") == "Evet"
        ),
        "is_athlete": answers.get("c1_sport_freq") in ("Haftada 3+", "Haftada 1-2"),
        "uses_supplements": answers.get("d1_supplements") == "Evet",
        "wants_steps": answers.get("c4_wants_steps") == "Evet",
        "wants_habits": "Rutin takibi" in goals,
        "wants_medication": (
            answers.get("b1_chronic") == "Evet"
            or answers.get("b2_medication") == "Evet"
            or "Sağlık-İlaç" in goals
        ),
        "wants_sport": (answers.get("c1_sport_freq") not in ("Hayır", None) or "Spor" in goals),
    }


def compute_profile_type(flags: dict[str, bool]) -> str:
    """Flag'lerden profil tipi hesapla."""
    if flags["has_chronic"] and flags["is_athlete"]:
        return PROFILE_MIXED
    if flags["has_chronic"]:
        return PROFILE_CHRONIC
    if flags["is_athlete"]:
        return PROFILE_ATHLETE
    return PROFILE_GENERAL


# Profil → açılacak bot'lar
PROFILE_BOTS: dict[str, list[BotKey]] = {
    PROFILE_CHRONIC: [BotKey.MEDICATION, BotKey.HABIT],
    PROFILE_ATHLETE: [BotKey.SPORT, BotKey.SUPPLEMENT, BotKey.STEP, BotKey.HABIT],
    PROFILE_MIXED: [
        BotKey.MEDICATION,
        BotKey.SPORT,
        BotKey.SUPPLEMENT,
        BotKey.STEP,
        BotKey.HABIT,
    ],
    PROFILE_GENERAL: [BotKey.HABIT, BotKey.STEP],
}


async def apply_profile_preferences(
    session: AsyncSession, user_id: int, profile_type: str, flags: dict[str, bool]
) -> None:
    """Profil tipine göre bot preference'larını aç.

    Sadece açar, kapatmaz — kullanıcının manuel kapattığı korunur.
    Flag override'ları: uses_supplements, wants_steps her zaman açar.
    """
    bots_to_enable = set(PROFILE_BOTS.get(profile_type, []))

    # Flag override'ları
    if flags.get("uses_supplements"):
        bots_to_enable.add(BotKey.SUPPLEMENT)
    if flags.get("wants_steps"):
        bots_to_enable.add(BotKey.STEP)
    if flags.get("wants_medication"):
        bots_to_enable.add(BotKey.MEDICATION)
    if flags.get("wants_sport"):
        bots_to_enable.add(BotKey.SPORT)

    for bot_key in bots_to_enable:
        await preference_service.toggle_preference(session, user_id, bot_key, enabled=True)


async def finalize_onboarding(
    session: AsyncSession, user_id: int, answers: dict[str, str]
) -> tuple[str, dict[str, bool]]:
    """Test bitti: kaydet, profil hesapla, preference ayarla.

    Returns (profile_type, flags).
    """
    # 1. Tüm cevapları kaydet
    for key, value in answers.items():
        await save_answer(session, user_id, key, value)

    # 2. Flag + profil
    flags = compute_flags(answers)
    profile_type = compute_profile_type(flags)

    # 3. User güncelle
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one()
    user.profile_type = profile_type
    user.onboarding_completed_at = now_in("UTC")
    user.onboarding_skipped = False

    # 4. Preference'ları ayarla
    await apply_profile_preferences(session, user_id, profile_type, flags)

    # 5. Step goal (C4a)
    step_goal = answers.get("c4a_step_goal")
    if step_goal:
        try:
            await step_service.update_daily_target(session, user_id, int(step_goal))
        except ValueError:
            pass  # geçersiz girdi: UI katmanında validate edilecek

    await session.flush()
    return profile_type, flags


async def skip_onboarding(session: AsyncSession, user_id: int) -> None:
    """Kullanıcı testi atladı."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one()
    user.onboarding_skipped = True
    await session.flush()


__all__ = [
    "ONBOARDING_QUESTIONS",
    "PROFILE_ATHLETE",
    "PROFILE_BOTS",
    "PROFILE_CHRONIC",
    "PROFILE_GENERAL",
    "PROFILE_MIXED",
    "apply_profile_preferences",
    "compute_flags",
    "compute_profile_type",
    "finalize_onboarding",
    "get_answers",
    "save_answer",
    "skip_onboarding",
]
