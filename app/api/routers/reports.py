"""Report endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.rate_limit import REPORTS_LIMIT, limiter
from app.api.schemas.report import (
    ReportDailySchema,
    ReportMonthlySchema,
    ReportStreakSchema,
    ReportWeeklySchema,
    ReportYearlySchema,
)
from app.core.timezone import now_in
from app.services import report_service, settings_service, streak_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/daily", response_model=ReportDailySchema)
@limiter.limit(REPORTS_LIMIT)
async def daily_report(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
    day: Annotated[date | None, Query(alias="date")] = None,
) -> ReportDailySchema:
    """Return the daily completion report for the authenticated user."""
    data = await report_service.generate_daily_report(session, user_id, day)
    return ReportDailySchema(**data)


@router.get("/weekly", response_model=ReportWeeklySchema)
@limiter.limit(REPORTS_LIMIT)
async def weekly_report(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
    week_start: Annotated[date | None, Query()] = None,
) -> ReportWeeklySchema:
    """Return the weekly completion report for the authenticated user."""
    data = await report_service.generate_weekly_report(session, user_id, week_start)
    return ReportWeeklySchema(**data)


@router.get("/monthly", response_model=ReportMonthlySchema)
@limiter.limit(REPORTS_LIMIT)
async def monthly_report(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
    year: Annotated[int | None, Query(ge=1)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
) -> ReportMonthlySchema:
    """Return the monthly completion report for the authenticated user."""
    if year is None or month is None:
        user = await settings_service.get_settings(session, user_id)
        current = now_in(user.timezone)
        year = year or current.year
        month = month or current.month
    report = await report_service.generate_monthly_report(session, user_id, year, month)
    return ReportMonthlySchema.from_report(report)


@router.get("/yearly", response_model=ReportYearlySchema)
@limiter.limit(REPORTS_LIMIT)
async def yearly_report(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> ReportYearlySchema:
    """Return the yearly completion report for the authenticated user."""
    if year is None:
        user = await settings_service.get_settings(session, user_id)
        year = now_in(user.timezone).year
    report = await report_service.generate_yearly_report(session, user_id, year)
    return ReportYearlySchema.from_report(report)


@router.get("/streak", response_model=ReportStreakSchema)
@limiter.limit(REPORTS_LIMIT)
async def streak_report(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
) -> ReportStreakSchema:
    """Return the current and longest completion streak for the authenticated user."""
    report = await streak_service.generate_streak_report(session, user_id)
    return ReportStreakSchema.from_report(report)
