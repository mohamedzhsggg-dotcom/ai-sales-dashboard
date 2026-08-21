"""Mock courier provider for testing."""

from __future__ import annotations

import random
from datetime import datetime, timezone

from app.services.couriers.base import (
    CourierProviderInterface,
    ShipmentRequest,
    ShipmentResult,
    TrackingEvent,
)


class MockCourierProvider(CourierProviderInterface):
    """In-memory mock courier for automated tests.

    Track shipments via self.shipments dict. No network calls.
    """

    def __init__(self) -> None:
        self.shipments: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return "mock"

    def create_shipment(self, request: ShipmentRequest) -> ShipmentResult:
        tracking = f"MOCK-{random.randint(100000, 999999)}"
        self.shipments[tracking] = {
            "status": "pending",
            "order_id": request.order_id,
            "created_at": datetime.now(timezone.utc),
            "events": [],
        }
        return ShipmentResult(
            tracking_number=tracking,
            courier_name="mock",
            status="pending",
            success=True,
        )

    def track_shipment(self, tracking_number: str) -> ShipmentResult:
        shipment = self.shipments.get(tracking_number)
        if not shipment:
            return ShipmentResult(
                success=False, error="Not found",
                tracking_number=tracking_number, courier_name="mock",
            )
        return ShipmentResult(
            tracking_number=tracking_number,
            courier_name="mock",
            status=shipment["status"],
            events=[
                TrackingEvent(
                    status=shipment["status"],
                    description=f"Shipment is {shipment['status']}",
                    timestamp=shipment.get("created_at"),
                )
            ],
            success=True,
        )

    def cancel_shipment(self, tracking_number: str) -> ShipmentResult:
        shipment = self.shipments.get(tracking_number)
        if not shipment:
            return ShipmentResult(
                success=False, error="Not found",
                tracking_number=tracking_number, courier_name="mock",
            )
        shipment["status"] = "cancelled"
        return ShipmentResult(
            tracking_number=tracking_number,
            courier_name="mock",
            status="cancelled",
            success=True,
        )

    def advance_status(self, tracking_number: str, new_status: str) -> None:
        """Test helper: advance a mock shipment to a new status."""
        if tracking_number in self.shipments:
            self.shipments[tracking_number]["status"] = new_status
