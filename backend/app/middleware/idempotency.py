"""Idempotency middleware.

Clients may send an `Idempotency-Key` header on mutating requests. The first
request executes and its response is stored; replaying the same key returns the
stored response without re-executing, preventing double order confirmation,
double stock deduction, etc.

Store is PostgreSQL (idempotency_keys table) for correctness; a Redis layer is
added in a later phase. Keys are scoped by tenant+user to prevent cross-tenant
replay.
"""

import json

from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.database import SessionLocal
from app.models import IdempotencyKey

_IDEMPOTENT_METHODS = {"POST", "PATCH", "PUT", "DELETE"}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        key = request.headers.get("Idempotency-Key")
        if not key or request.method not in _IDEMPOTENT_METHODS:
            return await call_next(request)

        identity = _identity(request)
        scoped_key = f"{identity}:{key}"

        db = SessionLocal()
        try:
            existing = db.query(IdempotencyKey).filter(IdempotencyKey.key == scoped_key).first()
            if existing and existing.response_json:
                return Response(
                    content=json.dumps(existing.response_json["body"]),
                    status_code=existing.response_json.get("status", 200),
                    media_type="application/json",
                )

            response = await call_next(request)

            if response.status_code < 400:
                body = b"".join([chunk async for chunk in response.body_iterator])
                parsed = None
                try:
                    parsed = json.loads(body) if body else None
                except (ValueError, TypeError):
                    parsed = None
                db.merge(IdempotencyKey(
                    key=scoped_key,
                    response_json={"status": response.status_code, "body": parsed or {}},
                ))
                db.commit()

                # Rebuild a fresh response (original body_iterator is consumed).
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                    background=response.background,
                )
            return response
        finally:
            db.close()


def _identity(request) -> str:
    user = getattr(request.state, "user_id", None)
    tenant = getattr(request.state, "tenant_id", None)
    return f"t{tenant or 0}u{user or 0}"