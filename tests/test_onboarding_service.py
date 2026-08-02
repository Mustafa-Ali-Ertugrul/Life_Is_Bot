"""Onboarding service tests."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BotKey, OnboardingAnswer, User
from app.services import onboarding_service, preference_service, step_service


async def _make_user(db_session: AsyncSession) -> User:
    user = User(name="test", consent_given=True, is_active=True, timezone="Europe/Istanbul")
    db_session.add(user)
    await db_session.flush()
    return user


async def test_save_answer_creates_row(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)

    answer = await onboarding_service.save_answer(db_session, user.id, "a1_gender", "Kadın")

    assert answer.id is not None
    assert answer.question_key == "a1_gender"
    assert answer.answer_value == "Kadın"


async def test_save_answer_upserts(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    first = await onboarding_service.save_answer(db_session, user.id, "a1_gender", "Kadın")
    second = await onboarding_service.save_answer(db_session, user.id, "a1_gender", "Erkek")

    assert second.id == first.id
    assert second.answer_value == "Erkek"
    count = await db_session.scalar(
        select(func.count())
        .select_from(OnboardingAnswer)
        .where(
            OnboardingAnswer.user_id == user.id,
            OnboardingAnswer.question_key == "a1_gender",
        )
    )
    assert count == 1


async def test_get_answers_returns_dict(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    await onboarding_service.save_answer(db_session, user.id, "a1_gender", "Kadın")
    await onboarding_service.save_answer(db_session, user.id, "b1_chronic", "Evet")

    answers = await onboarding_service.get_answers(db_session, user.id)

    assert answers == {"a1_gender": "Kadın", "b1_chronic": "Evet"}


def test_compute_flags_chronic() -> None:
    flags = onboarding_service.compute_flags({"b1_chronic": "Evet"})
    assert flags["has_chronic"] is True


def test_compute_flags_athlete() -> None:
    flags = onboarding_service.compute_flags({"c1_sport_freq": "Haftada 3+"})
    assert flags["is_athlete"] is True


def test_compute_flags_both() -> None:
    flags = onboarding_service.compute_flags({"b1_chronic": "Evet", "c1_sport_freq": "Haftada 1-2"})
    assert flags["has_chronic"] is True
    assert flags["is_athlete"] is True


def test_compute_flags_none() -> None:
    flags = onboarding_service.compute_flags({})
    assert all(value is False for value in flags.values())


def test_compute_profile_type_chronic() -> None:
    assert (
        onboarding_service.compute_profile_type({"has_chronic": True, "is_athlete": False})
        == "chronic"
    )


def test_compute_profile_type_athlete() -> None:
    assert (
        onboarding_service.compute_profile_type({"has_chronic": False, "is_athlete": True})
        == "athlete"
    )


def test_compute_profile_type_mixed() -> None:
    assert (
        onboarding_service.compute_profile_type({"has_chronic": True, "is_athlete": True})
        == "mixed"
    )


def test_compute_profile_type_general() -> None:
    assert (
        onboarding_service.compute_profile_type({"has_chronic": False, "is_athlete": False})
        == "general"
    )


async def test_apply_profile_preferences_chronic(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)

    await onboarding_service.apply_profile_preferences(
        db_session, user.id, "chronic", {"has_chronic": True}
    )

    assert await preference_service.is_enabled(db_session, user.id, BotKey.MEDICATION) is True
    assert await preference_service.is_enabled(db_session, user.id, BotKey.HABIT) is True


async def test_apply_profile_preferences_athlete(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)

    await onboarding_service.apply_profile_preferences(
        db_session, user.id, "athlete", {"is_athlete": True}
    )

    assert await preference_service.is_enabled(db_session, user.id, BotKey.SPORT) is True
    assert await preference_service.is_enabled(db_session, user.id, BotKey.SUPPLEMENT) is True
    assert await preference_service.is_enabled(db_session, user.id, BotKey.STEP) is True
    assert await preference_service.is_enabled(db_session, user.id, BotKey.HABIT) is True


async def test_finalize_onboarding_full_flow(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)

    profile_type, flags = await onboarding_service.finalize_onboarding(
        db_session, user.id, {"b1_chronic": "Evet"}
    )

    assert profile_type == "chronic"
    assert flags["has_chronic"] is True
    assert user.profile_type == "chronic"
    assert user.onboarding_completed_at is not None
    assert user.onboarding_skipped is False
    assert await preference_service.is_enabled(db_session, user.id, BotKey.MEDICATION) is True
    assert await preference_service.is_enabled(db_session, user.id, BotKey.HABIT) is True
    answers = await onboarding_service.get_answers(db_session, user.id)
    assert answers == {"b1_chronic": "Evet"}


async def test_finalize_onboarding_sets_step_goal(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)

    await onboarding_service.finalize_onboarding(
        db_session, user.id, {"c4_wants_steps": "Evet", "c4a_step_goal": "12000"}
    )

    settings = await step_service.get_settings(db_session, user.id)
    assert settings is not None
    assert settings.daily_target == 12000


async def test_skip_onboarding(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)

    await onboarding_service.skip_onboarding(db_session, user.id)

    assert user.onboarding_skipped is True
