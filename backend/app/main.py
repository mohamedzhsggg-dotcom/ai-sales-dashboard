import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.core.errors import RequestContextMiddleware, register_error_handlers
from app.core.logging import AccessLogMiddleware, setup_logging
from app.core.monitoring import MetricsMiddleware, init_sentry, metrics_response
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.ratelimit import RateLimitMiddleware
from app.database import engine
from app.api.routes import ai, auth, audit, categories, conversations, customers, dashboard, health, inventory, media, meta, orders, products, returns, settings as settings_router, shipments, social

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
init_sentry(settings.SENTRY_DSN)

# Legacy Google Sheets compatibility subscriber (removable with the legacy
# layer). When SHEETS_COMPAT_MODE is False this is a no-op on every event.
from app.services.legacy.subscriber import register_legacy_subscribers

register_legacy_subscribers()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic migrations (backend/migrations). Here we only
    # verify the database is reachable; tables are NOT created on startup.
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(AccessLogMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(orders.router, prefix=settings.API_PREFIX)
app.include_router(customers.router, prefix=settings.API_PREFIX)
app.include_router(products.router, prefix=settings.API_PREFIX)
app.include_router(categories.router, prefix=settings.API_PREFIX)
app.include_router(media.router, prefix=settings.API_PREFIX)
app.include_router(inventory.router, prefix=settings.API_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_PREFIX)
app.include_router(audit.router, prefix=settings.API_PREFIX)
app.include_router(shipments.router, prefix=settings.API_PREFIX)
app.include_router(returns.router, prefix=settings.API_PREFIX)
app.include_router(conversations.router, prefix=settings.API_PREFIX)
app.include_router(social.router, prefix=settings.API_PREFIX)
app.include_router(ai.router, prefix=settings.API_PREFIX)
app.include_router(meta.router)
app.include_router(settings_router.router, prefix=settings.API_PREFIX)
app.include_router(health.router)


@app.get("/metrics")
def metrics():
    return metrics_response()