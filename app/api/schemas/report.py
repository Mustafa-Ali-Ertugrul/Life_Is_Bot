"""Report response schemas."""

from datetime import date

from pydantic import BaseModel

from app.services.report_service import (
    MonthDaysReport,
    MonthlyBreakdown,
    MonthlyReport,
    YearlyReport,
)
from app.services.streak_service import StreakReport


class ReportDailySchema(BaseModel):
    date: date
    total: int
    completed: int
    missed: int
    unanswered: int
    completed_items: list[str]
    missed_items: list[str]
    step_steps: int | None
    step_goal: int | None


class ReportWeeklySchema(BaseModel):
    week_start: date
    week_end: date
    total: int
    completed: int
    missed: int
    unanswered: int
    compliance_rate: int
    best_day: int | None
    weakest_day: int | None


class ReportStreakSchema(BaseModel):
    user_id: int
    current: int
    longest: int
    today_completed: bool

    @classmethod
    def from_report(cls, report: StreakReport) -> "ReportStreakSchema":
        return cls(
            user_id=report.user_id,
            current=report.current,
            longest=report.longest,
            today_completed=report.today_completed,
        )


class ReportBotStatsSchema(BaseModel):
    bot_key: str
    total: int
    completed: int
    missed: int
    snoozed: int
    pending: int
    completion_rate: float


class ReportMonthlySchema(BaseModel):
    user_id: int
    year: int
    month: int
    bot_stats: list[ReportBotStatsSchema]
    total: int
    total_completed: int
    total_missed: int
    total_snoozed: int
    total_pending: int
    completion_rate: float

    @classmethod
    def from_report(cls, report: MonthlyReport) -> "ReportMonthlySchema":
        return cls(
            user_id=report.user_id,
            year=report.year,
            month=report.month,
            bot_stats=[
                ReportBotStatsSchema(
                    bot_key=stats.bot_key,
                    total=stats.total,
                    completed=stats.completed,
                    missed=stats.missed,
                    snoozed=stats.snoozed,
                    pending=stats.pending,
                    completion_rate=stats.completion_rate,
                )
                for stats in report.bot_stats
            ],
            total=report.total,
            total_completed=report.total_completed,
            total_missed=report.total_missed,
            total_snoozed=report.total_snoozed,
            total_pending=report.total_pending,
            completion_rate=report.completion_rate,
        )


class ReportMonthDaysSchema(BaseModel):
    user_id: int
    year: int
    month: int
    bot_key: str | None
    scheduled_days: list[date]
    completed_days: list[date]

    @classmethod
    def from_report(cls, report: MonthDaysReport) -> "ReportMonthDaysSchema":
        return cls(
            user_id=report.user_id,
            year=report.year,
            month=report.month,
            bot_key=report.bot_key,
            scheduled_days=report.scheduled_days,
            completed_days=report.completed_days,
        )


class ReportYearlyMonthSchema(BaseModel):
    month: int
    total: int
    completed: int
    missed: int
    snoozed: int
    pending: int
    completion_rate: float


class ReportYearlySchema(BaseModel):
    user_id: int
    year: int
    monthly: list[ReportYearlyMonthSchema]
    total: int
    total_completed: int
    total_missed: int
    total_snoozed: int
    total_pending: int
    completion_rate: float
    best_month: ReportYearlyMonthSchema | None
    worst_month: ReportYearlyMonthSchema | None

    @classmethod
    def from_report(cls, report: YearlyReport) -> "ReportYearlySchema":
        def _breakdown(month: MonthlyBreakdown) -> ReportYearlyMonthSchema:
            return ReportYearlyMonthSchema(
                month=month.month,
                total=month.total,
                completed=month.completed,
                missed=month.missed,
                snoozed=month.snoozed,
                pending=month.pending,
                completion_rate=month.completion_rate,
            )

        return cls(
            user_id=report.user_id,
            year=report.year,
            monthly=[_breakdown(m) for m in report.monthly],
            total=report.total,
            total_completed=report.total_completed,
            total_missed=report.total_missed,
            total_snoozed=report.total_snoozed,
            total_pending=report.total_pending,
            completion_rate=report.completion_rate,
            best_month=_breakdown(report.best_month) if report.best_month else None,
            worst_month=_breakdown(report.worst_month) if report.worst_month else None,
        )
