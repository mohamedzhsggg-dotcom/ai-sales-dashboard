"""Yalidine courier provider."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.services.couriers.base import (
    CourierProviderInterface,
    ShipmentRequest,
    ShipmentResult,
    TrackingEvent,
)

logger = logging.getLogger(__name__)

# Mapping from Yalidine status codes to our internal status names.
YALIDINE_STATUS_MAP = {
    "1": "pending",
    "2": "confirmed",
    "3": "shipped",
    "4": "out_for_delivery",
    "5": "delivered",
    "6": "returned",
    "7": "cancelled",
    "10": "on_hold",
}


class YalidineProvider(CourierProviderInterface):
    """Yalidine courier integration.

    Uses the Yalidine REST API (api.yalidine.app/v1).
    Authentication: token-based via Authorization header.
    """

    def __init__(self, api_token: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_settings()
        self._base_url = (base_url or settings.YALIDINE_API_BASE_URL).rstrip("/")
        self._token = api_token
        self._client: Optional[httpx.Client] = None

    @property
    def name(self) -> str:
        return "yalidine"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Token {self._token}"
        return h

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def create_shipment(self, request: ShipmentRequest) -> ShipmentResult:
        client = self._get_client()
        payload = {
            "wilaya": request.wilaya,
            "commune": request.commune or "",
            "phone": request.phone,
            "name": request.name,
            "address": request.address or "",
            "product_desc": request.product_description,
            "price": str(request.cod_amount),
            "shipping_price": str(request.shipping_fee),
            "delivery_type": "domicile" if request.delivery_method == "home" else "bureau",
            "note": request.notes or "",
        }
        try:
            resp = client.post(
                f"{self._base_url}/colis/",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            tracking = data.get("tracking", data.get("id", ""))
            return ShipmentResult(
                tracking_number=str(tracking),
                courier_name="yalidine",
                status="pending",
                raw=data,
                success=True,
            )
        except Exception as exc:
            logger.error("Yalidine create_shipment failed: %s", exc)
            return ShipmentResult(success=False, error=str(exc), courier_name="yalidine")

    def track_shipment(self, tracking_number: str) -> ShipmentResult:
        client = self._get_client()
        try:
            resp = client.get(
                f"{self._base_url}/colis/{tracking_number}/",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            status_code = str(data.get("status", "1"))
            status_name = YALIDINE_STATUS_MAP.get(status_code, "unknown")
            events = [
                TrackingEvent(
                    status=status_name,
                    description=data.get("status_display", data.get("message", "")),
                    timestamp=data.get("updated_at"),
                )
            ]
            return ShipmentResult(
                tracking_number=tracking_number,
                courier_name="yalidine",
                status=status_name,
                events=events,
                raw=data,
                success=True,
            )
        except Exception as exc:
            logger.error("Yalidine track_shipment failed: %s", exc)
            return ShipmentResult(success=False, error=str(exc), courier_name="yalidine")

    def cancel_shipment(self, tracking_number: str) -> ShipmentResult:
        client = self._get_client()
        try:
            resp = client.post(
                f"{self._base_url}/colis/{tracking_number}/annuler/",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return ShipmentResult(
                tracking_number=tracking_number,
                courier_name="yalidine",
                status="cancelled",
                success=True,
            )
        except Exception as exc:
            logger.error("Yalidine cancel_shipment failed: %s", exc)
            return ShipmentResult(success=False, error=str(exc), courier_name="yalidine")

    def health_check(self) -> bool:
        try:
            client = self._get_client()
            resp = client.get(f"{self._base_url}/", headers=self._headers(), timeout=5.0)
            return resp.status_code < 500
        except Exception:
            return False
