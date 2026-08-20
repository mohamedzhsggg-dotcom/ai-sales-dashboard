"""Standardized error responses and request-id correlation.

Every error returns the envelope:
    {"error": {"code": <str>, "message": <str>, "detail": <any>, "request_id": <str>}}
"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
    500: "internal_error",
    502: "bad_gateway",
    503: "service_unavailable",
}


def request_id() -> str:
    return uuid.uuid4().hex


def error_payload(status: int, message: str, detail=None, rid: str | None = None) -> dict:
    return {
        "error": {
            "code": _ERROR_CODES.get(status, "error"),
            "message": message,
            "detail": detail,
            "request_id": rid or request_id(),
        }
    }


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", request_id())


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.status_code, str(exc.detail), rid=_rid(request)),
    )


async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(422, "Validation error", exc.errors(), rid=_rid(request)),
    )


async def _integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.exception("Integrity error")
    return JSONResponse(
        status_code=409,
        content=error_payload(409, "A record with these values already exists", rid=_rid(request)),
    )


async def _operational_exception_handler(request: Request, exc: OperationalError) -> JSONResponse:
    logger.exception("Database operational error")
    return JSONResponse(
        status_code=503,
        content=error_payload(503, "Database unavailable", rid=_rid(request)),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content=error_payload(500, "Internal server error", rid=_rid(request)),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(IntegrityError, _integrity_exception_handler)
    app.add_exception_handler(OperationalError, _operational_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


class RequestContextMiddleware:
    """Attaches a request_id to every request (used by logs and error envelope)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        import asyncio

        rid = uuid.uuid4().hex
        scope["state"] = {**getattr(scope, "state", {}), "request_id": rid}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)