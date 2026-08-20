"""Structured JSON logging with request correlation.

Access logs and app logs emit single-line JSON with request_id/tenant_id/user_id
so they can be shipped to any log aggregator. Falls back to plain logging if
JSON serialization is not available (never crashes the app).
"""

import json
import logging
import sys
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "tenant_id", "user_id", "method", "path", "status", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        try:
            return json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError):
            return json.dumps({**payload, "message": str(record.getMessage())})


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


def _request_record(request, **extra) -> dict:
    state = getattr(request, "state", None)
    base = {
        "request_id": getattr(state, "request_id", uuid.uuid4().hex),
        "tenant_id": getattr(state, "tenant_id", None),
        "user_id": getattr(state, "user_id", None),
        "method": request.method,
        "path": request.url.path,
    }
    base.update(extra)
    return base


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Logs one JSON line per request with status + duration."""

    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logging.getLogger("access").info(
            "",
            extra=_request_record(request, status=response.status_code, duration_ms=duration_ms),
        )
        return response