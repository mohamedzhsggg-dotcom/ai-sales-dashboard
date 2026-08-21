"""Server-side order status transition validation.

Defines legal status transitions and enforces rules. Prevents arbitrary
free-form status patches.
"""

from __future__ import annotations

# Legal transitions: from_status -> set of allowed to_status values
LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "new": {"confirmed", "cancelled", "on_hold"},
    "confirmed": {"shipped", "cancelled", "on_hold"},
    "shipped": {"delivered", "cancelled", "returned"},
    "delivered": {"returned"},
    "returned": {"refunded"},
    "on_hold": {"new", "confirmed", "cancelled"},
    "cancelled": set(),  # terminal
    "refunded": set(),   # terminal
}

# Statuses that require a reason/note
REQUIRES_REASON = {"cancelled", "returned", "on_hold"}

# Legacy status mapping for unknown statuses
LEGACY_STATUS_MAP = {
    "pending": "new",
    "processing": "confirmed",
    "sent": "shipped",
    "livré": "delivered",
    "annulé": "cancelled",
}


class InvalidTransition(Exception):
    def __init__(self, from_status: str, to_status: str):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Cannot transition from '{from_status}' to '{to_status}'")


def validate_transition(from_status: str, to_status: str) -> None:
    """Raise InvalidTransition if the transition is not allowed."""
    allowed = LEGAL_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise InvalidTransition(from_status, to_status)


def normalize_status(status: str) -> str:
    """Map legacy/unknown statuses to a safe default."""
    return LEGACY_STATUS_MAP.get(status, status)


def needs_reason(to_status: str) -> bool:
    """Return True if a reason/note is required for this transition."""
    return to_status in REQUIRES_REASON
