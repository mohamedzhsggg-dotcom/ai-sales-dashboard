"""Prometheus metrics + optional Sentry init.

Exposes a /metrics endpoint for scraping. Metrics are in-process counters; no
external process is required. Sentry is a no-op unless SENTRY_DSN is configured.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

    _METRICS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _METRICS_AVAILABLE = False

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)
IN_FLIGHT = Gauge("http_requests_in_flight", "In-flight HTTP requests")


def init_sentry(dsn: str = "") -> None:
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.1,
            integrations=[
                StarletteIntegration(transaction_style="endpoint"),
                FastApiIntegration(transaction_style="endpoint"),
            ],
        )
    except Exception:  # pragma: no cover
        pass


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not _METRICS_AVAILABLE:
            return await call_next(request)
        path = request.url.path
        IN_FLIGHT.inc()
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        IN_FLIGHT.dec()
        REQUEST_COUNT.labels(method=request.method, path=path, status=response.status_code).inc()
        REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
        return response


def metrics_response() -> PlainTextResponse:
    if not _METRICS_AVAILABLE:
        return PlainTextResponse("metrics disabled", status_code=501)
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)