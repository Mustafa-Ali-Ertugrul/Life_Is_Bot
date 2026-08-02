"""Report endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.schemas.report import (
    ReportDailySchema,
    ReportMonthlySchema,
    ReportWeeklySchema,
)
from app.core.timezone import now_in
from app.services import report_service, settings_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/daily", response_model=ReportDailySchema)
async def daily_report(
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
    day: Annotated[date | None, Query(alias="date")] = None,
) -> ReportDailySchema:
    """Return the daily completion report for the authenticated user."""
    data = await report_service.generate_daily_report(session, user_id, day)
    return ReportDailySchema(**data)


@router.get("/weekly", response_model=ReportWeeklySchema)
async def weekly_report(
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user)],
    week_start: Annotated[date | None, Query()] = None,
) -> ReportWeeklySchema:
    """Return the weekly completion report for the authenticated user."""
    data = await report_service.generate_weekly_report(session, user_id, week_start)
    return ReportWeeklySchema(**data)


@router.get("/monthly", response_model=ReportMonthlySchema)
async def monthly_report(
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
