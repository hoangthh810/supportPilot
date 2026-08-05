from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.apps.support_api.core.correlation import get_correlation_id


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    retryable: bool
    correlation_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


def _error_response(request: Request, error: ApiError) -> JSONResponse:
    envelope = ErrorEnvelope(
        code=error.code,
        message=error.message,
        retryable=error.retryable,
        correlation_id=get_correlation_id(request),
        details=error.details,
    )
    return JSONResponse(status_code=error.status_code, content=envelope.model_dump(mode="json"))


async def api_error_handler(request: Request, exception: Exception) -> JSONResponse:
    if not isinstance(exception, ApiError):
        raise TypeError("api_error_handler received an unsupported exception")
    return _error_response(request, exception)


async def validation_error_handler(
    request: Request, exception: Exception
) -> JSONResponse:
    if not isinstance(exception, RequestValidationError):
        raise TypeError("validation_error_handler received an unsupported exception")
    details = {
        "errors": [
            {"location": list(item["loc"]), "type": item["type"], "message": item["msg"]}
            for item in exception.errors()
        ]
    }
    return _error_response(
        request,
        ApiError(
            status_code=422,
            code="REQUEST_VALIDATION_ERROR",
            message="The request is invalid.",
            details=details,
        ),
    )


async def unhandled_error_handler(request: Request, exception: Exception) -> JSONResponse:
    del exception
    return _error_response(
        request,
        ApiError(
            status_code=500,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

