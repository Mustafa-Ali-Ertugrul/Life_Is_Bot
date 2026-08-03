"""Step tracker API schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


def _validate_days_of_week(value: str) -> str:
    days = [part.strip() for part in value.split(",") if part.strip()]
    if not days:
        raise ValueError("days_of_week must not be empty")
    for part in days:
        if not part.isdigit() or not 1 <= int(part) <= 7:
            raise ValueError("days_of_week must contain numbers between 1 and 7")
    return ",".join(days)


class StepSettingsUpdate(BaseModel):
    daily_target: int | None = Field(default=None, ge=0, le=100000)
    reminder_hour: int | None = Field(default=None, ge=0, le=23)
    reminder_minute: int | None = Field(default=None, ge=0, le=59)
    days_of_week: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None

    @field_validator("days_of_week")
    @classmethod
    def _check_days(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_days_of_week(value)


class StepSettingsResponse(BaseModel):
    id: int
    daily_target: int
    reminder_hour: int
    reminder_minute: int
    days_of_week: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StepLogCreate(BaseModel):
    steps: int = Field(ge=0, le=200000)
    log_date: date


class StepLogResponse(BaseModel):
    id: int
    steps: int
    log_date: date
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
