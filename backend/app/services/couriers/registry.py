"""Courier provider registry."""

from __future__ import annotations

from typing import Optional

from app.services.couriers.base import CourierProviderInterface

_registry: dict[str, CourierProviderInterface] = {}


def register_provider(provider: CourierProviderInterface) -> None:
    """Register a courier provider by name."""
    _registry[provider.name.lower()] = provider


def get_provider(name: Optional[str] = None) -> Optional[CourierProviderInterface]:
    """Get a registered provider by name. If name is None, returns the first registered."""
    if not _registry:
        return None
    if name is None:
        return next(iter(_registry.values()))
    return _registry.get(name.lower())


def list_providers() -> list[str]:
    """Return names of all registered providers."""
    return list(_registry.keys())
