"""Health check response schema."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: bool
    version: str
