from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class CommerceApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_response(request: Request, error: CommerceApiError) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", "corr_unavailable")
    return JSONResponse(
        status_code=error.status_code,
        content={
            "code": error.code,
            "message": error.message,
            "retryable": False,
            "correlation_id": correlation_id,
            "details": error.details,
        },
    )


async def commerce_error_handler(request: Request, exception: Exception) -> JSONResponse:
    if not isinstance(exception, CommerceApiError):
        raise TypeError("commerce_error_handler received an unsupported exception")
    return error_response(request, exception)


async def validation_error_handler(request: Request, exception: Exception) -> JSONResponse:
    if not isinstance(exception, RequestValidationError):
        raise TypeError("validation_error_handler received an unsupported exception")
    return error_response(
        request,
        CommerceApiError(
            status_code=422,
            code="REQUEST_VALIDATION_ERROR",
            message="The request is invalid.",
            details={
                "errors": [
                    {
                        "location": list(item["loc"]),
                        "type": item["type"],
                        "message": item["msg"],
                    }
                    for item in exception.errors()
                ]
            },
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CommerceApiError, commerce_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
