"""Ukrposhta REST API client — https://www.ukrposhta.ua/ua/developer"""

from __future__ import annotations

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)
BASE_URL = "https://www.ukrposhta.ua/ecom/0.0.1"


class UkrPoshtaClient:
    """Client for Ukrposhta ecommerce API (shipments + tracking)."""

    def __init__(self) -> None:
        self._token = getattr(settings, "UKRPOSHTA_TOKEN", "")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _post(self, path: str, payload: dict) -> dict:
        if not self._token:
            logger.warning("UkrPoshta: UKRPOSHTA_TOKEN not configured")
            return {}
        try:
            resp = httpx.post(
                f"{BASE_URL}{path}",
                json=payload,
                headers=self._headers,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("UkrPoshta POST %s error: %s", path, exc)
            return {}

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self._token:
            logger.warning("UkrPoshta: UKRPOSHTA_TOKEN not configured")
            return {}
        try:
            resp = httpx.get(
                f"{BASE_URL}{path}",
                params=params,
                headers=self._headers,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("UkrPoshta GET %s error: %s", path, exc)
            return {}

    def create_shipment(self, order) -> str | None:
        """
        Create shipment via Ukrposhta and return barcode.
        Returns barcode string or None on failure.
        """
        if not self._token:
            return None

        total = float(order.total)
        weight = sum(
            float(getattr(item.product, "weight", 0) or 0.3)
            for item in order.items.select_related("product").all()
        ) or 0.3

        payload = {
            "sender": {
                "name": getattr(settings, "SITE_NAME", "СвітПК"),
                "phone": getattr(settings, "SITE_PHONE", ""),
                "postcode": getattr(settings, "UP_SENDER_POSTCODE", ""),
                "address": getattr(settings, "UP_SENDER_ADDRESS", ""),
                "city": getattr(settings, "UP_SENDER_CITY", ""),
            },
            "recipient": {
                "name": f"{order.first_name} {order.last_name}".strip(),
                "phone": order.phone,
                "postcode": getattr(order, "postcode", ""),
                "address": order.warehouse or "",
                "city": order.city or "",
            },
            "deliveryType": "W2D",  # warehouse to door
            "weight": round(weight * 1000),  # in grams
            "declaredPrice": int(total),
            "description": f"Замовлення #{order.pk}",
        }

        data = self._post("/shipments", payload)
        barcode = data.get("barcode") or data.get("shipmentGroupBarcode")
        if barcode:
            logger.info("UkrPoshta shipment created: %s for order #%s", barcode, order.pk)
            return str(barcode)
        logger.error("UkrPoshta create_shipment failed for order #%s: %s", order.pk, data)
        return None

    def track(self, barcode: str) -> dict:
        """
        Track a shipment by barcode.
        Returns status dict with keys: status, statusCode, date, etc.
        """
        data = self._get(f"/shipments/{barcode}/statuses")
        statuses = data.get("data") or []
        if isinstance(statuses, list) and statuses:
            return statuses[-1]
        return data

    def get_shipment(self, barcode: str) -> dict:
        return self._get(f"/shipments/{barcode}")
