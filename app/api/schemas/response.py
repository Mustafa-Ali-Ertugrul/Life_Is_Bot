"""Schemas for mobile notification responses."""

from pydantic import BaseModel, Field, field_validator

from app.models import ResponseType

_MOBILE_RESPONSES = {
    ResponseType.TAKEN,
    ResponseType.NOT_TAKEN,
    ResponseType.DONE,
    ResponseType.NOT_DONE,
    ResponseType.SKIPPED,
}


class ResponseCreate(BaseModel):
    related_type: str = Field(min_length=1, max_length=64)
    related_id: int = Field(ge=1)
    response: ResponseType

    @field_validator("response")
    @classmethod
    def _response_allowed(cls, value: ResponseType) -> ResponseType:
        if value not in _MOBILE_RESPONSES:
            raise ValueError("response tipi mobil için desteklenmiyor")
        return value


class ResponseOut(BaseModel):
    event_id: int
    status: str
    response: str
    source: str
