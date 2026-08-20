"""In-process domain event bus.

Core domain services publish typed events *after* committing their PostgreSQL
transaction. The legacy Google Sheets compatibility layer subscribes to mirror
a minimal set of cells without core business logic ever depending on Sheets.
Removing Sheets = removing the subscriber, nothing else changes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

Handler = Callable[[str, dict[str, Any]], None]

# Event names (single source of truth for subscribers).
ORDER_STATUS_CHANGED = "order.status.changed"
STOCK_CHANGED = "stock.changed"
ORDER_CONFIRMED = "order.confirmed"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        self._subscribers[event].append(handler)

    def publish(self, event: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        for handler in list(self._subscribers.get(event, [])):
            try:
                handler(event, payload)
            except Exception:
                logger.exception("Event handler failed for %s", event)


bus = EventBus()