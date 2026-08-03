"""Sport plan API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _validate_days_of_week(value: str) -> str:
    days = [part.strip() for part in value.split(",") if part.strip()]
    if not days:
        raise ValueError("days_of_week must not be empty")
    for part in days:
        if not part.isdigit() or not 1 <= int(part) <= 7:
            raise ValueError("days_of_week must contain numbers between 1 and 7")
    return ",".join(days)


class SportCreate(BaseModel):
    sport_type: str = Field(min_length=1, max_length=64)
    target_hour: int = Field(ge=0, le=23)
    target_minute: int = Field(ge=0, le=59)
    days_of_week: str = Field(default="1,2,3,4,5,6,7", max_length=32)

    @field_validator("days_of_week")
    @classmethod
    def _check_days(cls, value: str) -> str:
        return _validate_days_of_week(value)


class SportUpdate(BaseModel):
    sport_type: str | None = Field(default=None, min_length=1, max_length=64)
    target_hour: int | None = Field(default=None, ge=0, le=23)
    target_minute: int | None = Field(default=None, ge=0, le=59)
    days_of_week: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None

    @field_validator("days_of_week")
    @classmethod
    def _check_days(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_days_of_week(value)


class SportResponse(BaseModel):
    id: int
    sport_type: str
    target_hour: int
    target_minute: int
    days_of_week: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
