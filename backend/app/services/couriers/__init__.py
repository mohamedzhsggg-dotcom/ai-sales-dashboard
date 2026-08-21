"""Courier provider abstraction layer.

Provides a pluggable registry for courier integrations (Yalidine, etc.).
Each provider implements CourierProviderInterface for create_shipment,
track_shipment, and cancel_shipment operations.
"""

from app.services.couriers.base import CourierProviderInterface, ShipmentRequest, ShipmentResult, TrackingEvent
from app.services.couriers.registry import get_provider, register_provider

__all__ = [
    "CourierProviderInterface",
    "ShipmentRequest",
    "ShipmentResult",
    "TrackingEvent",
    "get_provider",
    "register_provider",
]
