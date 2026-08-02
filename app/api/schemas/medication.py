"""Medication plan API schemas."""

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


class MedicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    dose: str | None = Field(default=None, max_length=80)
    with_food: str = Field(default="any", pattern="^(empty|full|any)$")
    target_hour: int = Field(ge=0, le=23)
    target_minute: int = Field(ge=0, le=59)
    days_of_week: str = Field(default="1,2,3,4,5,6,7", max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("days_of_week")
    @classmethod
    def _check_days(cls, value: str) -> str:
        return _validate_days_of_week(value)


class MedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    dose: str | None = Field(default=None, max_length=80)
    with_food: str | None = Field(default=None, pattern="^(empty|full|any)$")
    target_hour: int | None = Field(default=None, ge=0, le=23)
    target_minute: int | None = Field(default=None, ge=0, le=59)
    days_of_week: str | None = Field(default=None, max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("days_of_week")
    @classmethod
    def _check_days(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_days_of_week(value)


class MedicationResponse(BaseModel):
    id: int
    name: str
    dose: str | None
    with_food: str
    target_hour: int
    target_minute: int
    days_of_week: str
    start_date: date | None
    end_date: date | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
