"""Onboarding API router: 20 soruluk başlangıç değerlendirme testi (mobil)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.rate_limit import CRUD_LIMIT, limiter
from app.core.onboarding_questions import (
    ONBOARDING_QUESTIONS,
    OnboardingQuestion,
    QuestionType,
    get_next_question,
)
from app.models import User
from app.services import onboarding_service

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

MIN_STEP_GOAL = 1000
MAX_STEP_GOAL = 100000


class QuestionOut(BaseModel):
    index: int
    total: int
    key: str
    text: str
    question_type: str
    options: list[str]


class CompletionOut(BaseModel):
    profile_type: str
    enabled_bots: list[str]
    step_goal: int | None


class StatusOut(BaseModel):
    completed: bool
    skipped: bool
    question: QuestionOut | None
    answers: dict[str, str]


class AnswerIn(BaseModel):
    question_key: str = Field(min_length=1, max_length=30)
    answer_value: str = Field(min_length=1, max_length=100)


class AnswerOut(BaseModel):
    done: bool
    next: QuestionOut | None
    result: CompletionOut | None


def _question_out(index: int) -> QuestionOut:
    question = ONBOARDING_QUESTIONS[index]
    return QuestionOut(
        index=index,
        total=len(ONBOARDING_QUESTIONS),
        key=question.key,
        text=question.text,
        question_type=question.question_type.value,
        options=list(question.options),
    )


def _question_index(question_key: str) -> int | None:
    for i, question in enumerate(ONBOARDING_QUESTIONS):
        if question.key == question_key:
            return i
    return None


def _first_pending_question(answers: dict[str, str]) -> int | None:
    for i, question in enumerate(ONBOARDING_QUESTIONS):
        if question.key in answers:
            continue
        if question.condition is not None and not question.condition(answers):
            continue
        return i
    return None


def _validate_value(question: OnboardingQuestion, answer_value: str) -> str:
    if question.question_type is not QuestionType.NUMBER_INPUT:
        return answer_value
    raw = answer_value.strip()
    if "-" in raw:
        raise HTTPException(status_code=422, detail="Geçerli bir sayı girin")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise HTTPException(status_code=422, detail="Geçerli bir sayı girin")
    value = int(digits)
    if not MIN_STEP_GOAL <= value <= MAX_STEP_GOAL:
        raise HTTPException(status_code=422, detail="Adım hedefi 1000-100000 arasında olmalı")
    return str(value)


async def _get_user(db: AsyncSession, user_id: int) -> User:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return user


@router.get("", response_model=StatusOut)
@limiter.limit(CRUD_LIMIT)
async def onboarding_status(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
) -> StatusOut:
    """Onboarding durumu: tamamlanmadıysa sıradaki soruyu döndür."""
    user = await _get_user(db, user_id)
    answers = await onboarding_service.get_answers(db, user_id)

    question = None
    if user.onboarding_completed_at is None and not user.onboarding_skipped:
        pending = _first_pending_question(answers)
        if pending is not None:
            question = _question_out(pending)

    return StatusOut(
        completed=user.onboarding_completed_at is not None,
        skipped=bool(user.onboarding_skipped),
        question=question,
        answers=answers,
    )


@router.post("/answer", response_model=AnswerOut)
@limiter.limit(CRUD_LIMIT)
async def submit_answer(
    body: AnswerIn,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
) -> AnswerOut:
    """Cevabı kaydet; sonraki soruyu veya testi bitiren sonucu döndür."""
    index = _question_index(body.question_key)
    if index is None:
        raise HTTPException(status_code=400, detail=f"Geçersiz soru: {body.question_key}")

    question = ONBOARDING_QUESTIONS[index]
    value = _validate_value(question, body.answer_value)

    await onboarding_service.save_answer(db, user_id, question.key, value)
    answers = await onboarding_service.get_answers(db, user_id)

    next_step = get_next_question(index, answers)
    if next_step is not None:
        await db.commit()
        return AnswerOut(done=False, next=_question_out(next_step[0]), result=None)

    user = await _get_user(db, user_id)
    if user.onboarding_completed_at is None:
        profile_type, flags = await onboarding_service.finalize_onboarding(db, user_id, answers)
    else:
        flags = onboarding_service.compute_flags(answers)
        profile_type = onboarding_service.compute_profile_type(flags)
    await db.commit()

    enabled = onboarding_service.compute_enabled_bots(profile_type, flags)
    step_goal = None
    raw_goal = answers.get("c4a_step_goal")
    if raw_goal is not None:
        try:
            step_goal = int(raw_goal)
        except ValueError:
            step_goal = None

    return AnswerOut(
        done=True,
        next=None,
        result=CompletionOut(
            profile_type=profile_type,
            enabled_bots=[bot.value for bot in enabled],
            step_goal=step_goal,
        ),
    )


@router.post("/skip", response_model=StatusOut)
@limiter.limit(CRUD_LIMIT)
async def skip_onboarding(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
) -> StatusOut:
    """Testi atla; mobil doğrudan ana ekrana geçer."""
    await onboarding_service.skip_onboarding(db, user_id)
    await db.commit()
    answers = await onboarding_service.get_answers(db, user_id)
    return StatusOut(completed=False, skipped=True, question=None, answers=answers)
