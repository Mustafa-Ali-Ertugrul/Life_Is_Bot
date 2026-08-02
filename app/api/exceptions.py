"""Map application exceptions to HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppError, InvalidStateError, NotFoundError, PermissionDeniedError

_STATUS_MAP: dict[type[AppError], int] = {
    NotFoundError: 404,
    InvalidStateError: 422,
    PermissionDeniedError: 403,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Register AppError subclasses with their HTTP status codes."""

    @app.exception_handler(AppError)
    def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        status = 400
        for cls in type(exc).__mro__:
            if cls in _STATUS_MAP:
                status = _STATUS_MAP[cls]
                break
        return JSONResponse(status_code=status, content={"detail": str(exc)})
