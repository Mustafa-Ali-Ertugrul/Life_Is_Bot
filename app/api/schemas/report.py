"""Report response schemas."""

from datetime import date

from pydantic import BaseModel

from app.services.report_service import MonthlyReport


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
