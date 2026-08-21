"""Abstract base class for courier providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ShipmentRequest:
    """Data needed to create a shipment with a courier."""
    order_id: int
    tenant_id: int
    phone: str
    name: str
    wilaya: str
    commune: Optional[str] = None
    address: Optional[str] = None
    product_description: str = ""
    cod_amount: int = 0
    shipping_fee: int = 0
    delivery_method: str = "home"
    notes: Optional[str] = None
    items: list[dict] = field(default_factory=list)


@dataclass
class TrackingEvent:
    """A single tracking status event."""
    status: str
    description: str = ""
    timestamp: Optional[datetime] = None
    location: Optional[str] = None


@dataclass
class ShipmentResult:
    """Result of a shipment creation or tracking query."""
    tracking_number: Optional[str] = None
    courier_name: str = ""
    status: str = "pending"
    events: list[TrackingEvent] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class CourierProviderInterface(ABC):
    """Abstract interface for courier providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g. 'yalidine')."""

    @abstractmethod
    def create_shipment(self, request: ShipmentRequest) -> ShipmentResult:
        """Create a new shipment with the courier."""

    @abstractmethod
    def track_shipment(self, tracking_number: str) -> ShipmentResult:
        """Get current tracking status for a shipment."""

    @abstractmethod
    def cancel_shipment(self, tracking_number: str) -> ShipmentResult:
        """Cancel a shipment."""

    def health_check(self) -> bool:
        """Check if the provider is reachable. Default: always True."""
        return True
