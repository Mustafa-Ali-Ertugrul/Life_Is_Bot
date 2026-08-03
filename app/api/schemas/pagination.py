"""Generic pagination schema and helper."""

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


def paginate[T](items: list[T], limit: int, offset: int) -> PaginatedResponse[T]:
    return PaginatedResponse(
        items=items[offset : offset + limit], total=len(items), limit=limit, offset=offset
    )


__all__ = ["PaginatedResponse", "paginate"]
