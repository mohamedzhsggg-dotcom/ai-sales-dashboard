"""Liveness (/health) and readiness (/ready) endpoints.

/health: process is up (always 200).
/ready:  dependency checks — PostgreSQL connectivity (required) and Redis
         (optional; reports degraded but still 200 so the app stays routable).
"""

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.database import engine

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok", "app": "AI Sales Dashboard"}


@router.get("/ready")
def ready(response: Response):
    checks = {}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
        response.status_code = 503

    try:
        from app.middleware.ratelimit import _client

        if _client is not None:
            _client.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "disabled"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"degraded: {type(exc).__name__}"

    overall = "ok" if checks.get("database") == "ok" else "unhealthy"
    return {"status": overall, "checks": checks}