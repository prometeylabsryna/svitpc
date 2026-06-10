"""Ukrposhta REST API client — https://www.ukrposhta.ua/ua/developer"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

import httpx
from django.conf import settings

from apps.shipping.helpers import (
    DEFAULT_PARCEL_HEIGHT_CM,
    DEFAULT_PARCEL_LENGTH_CM,
    DEFAULT_PARCEL_WIDTH_CM,
)

logger = logging.getLogger(__name__)
BASE_URL = "https://www.ukrposhta.ua/ecom/0.0.1"
UP_DELIVERED_STATUSES = {"DELIVERED", "HANDED_OVER"}


class UkrPoshtaClient:
    """Client for Ukrposhta ecommerce API (pricing, shipments, tracking)."""

    def __init__(self) -> None:
        self._bearer = getattr(settings, "UKRPOSHTA_BEARER", "") or getattr(settings, "UKRPOSHTA_TOKEN", "")
        self._token = getattr(settings, "UKRPOSHTA_TOKEN", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._bearer and self._token)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._bearer}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        params: dict | None = None,
        use_counterparty_token: bool = False,
    ) -> dict | list:
        if not self._bearer:
            logger.warning("UkrPoshta: UKRPOSHTA_BEARER not configured")
            return {}

        query = dict(params or {})
        if use_counterparty_token:
            if not self._token:
                logger.warning("UkrPoshta: UKRPOSHTA_TOKEN not configured")
                return {}
            query["token"] = self._token

        url = f"{BASE_URL}{path}"
        try:
            resp = httpx.request(
                method,
                url,
                json=payload,
                params=query or None,
                headers=self._headers,
                timeout=30,
            )
            resp.raise_for_status()
            if not resp.content:
                return {}
            return resp.json()
        except Exception as exc:
            logger.error("UkrPoshta %s %s error: %s", method, path, exc)
            return {}

    def lookup_postoffice(self, postcode: str) -> dict | None:
        """Resolve post office details by postcode (creates address record)."""
        postcode = (postcode or "").strip()
        if not postcode.isdigit() or len(postcode) != 5:
            return None

        data = self._request("POST", "/addresses", payload={"postcode": postcode})
        if isinstance(data, dict) and data.get("id"):
            return data
        return None

    def calc_delivery_price(
        self,
        recipient_postcode: str,
        weight_kg: float,
        declared_value: int = 500,
    ) -> Decimal | None:
        """Estimate delivery price via /domestic/delivery-price."""
        sender_postcode = getattr(settings, "UP_SENDER_POSTCODE", "")
        recipient_postcode = (recipient_postcode or "").strip()
        if not sender_postcode or not recipient_postcode:
            return None

        weight_g = max(int(round(weight_kg * 1000)), 100)
        payload = {
            "addressFrom": {"postcode": sender_postcode},
            "addressTo": {"postcode": recipient_postcode},
            "type": "EXPRESS",
            "deliveryType": "W2W",
            "validate": True,
            "weight": weight_g,
            "length": DEFAULT_PARCEL_LENGTH_CM,
            "width": DEFAULT_PARCEL_WIDTH_CM,
            "height": DEFAULT_PARCEL_HEIGHT_CM,
            "parcels": [
                {
                    "weight": weight_g,
                    "length": DEFAULT_PARCEL_LENGTH_CM,
                    "width": DEFAULT_PARCEL_WIDTH_CM,
                    "height": DEFAULT_PARCEL_HEIGHT_CM,
                }
            ],
            "declaredPrice": declared_value,
        }
        data = self._request("POST", "/domestic/delivery-price", payload=payload)
        if isinstance(data, dict) and data.get("deliveryPrice") is not None:
            return Decimal(str(data["deliveryPrice"]))
        return None

    def _normalize_phone(self, phone: str) -> str:
        digits = re.sub(r"\D", "", phone or "")
        if digits.startswith("380"):
            return f"+{digits}"
        if digits.startswith("0") and len(digits) == 10:
            return f"+38{digits}"
        if len(digits) == 9:
            return f"+380{digits}"
        return phone

    def _order_weight_g(self, order) -> int:
        from apps.shipping.helpers import order_weight_kg

        return max(int(round(order_weight_kg(order) * 1000)), 100)

    def create_recipient_client(self, order) -> str | None:
        """Create Ukrposhta recipient client; return client UUID."""
        address = self.lookup_postoffice(order.postcode)
        if not address:
            logger.error("UkrPoshta: invalid recipient postcode for order #%s", order.pk)
            return None

        payload = {
            "type": "INDIVIDUAL",
            "firstName": order.first_name,
            "lastName": order.last_name,
            "phoneNumber": self._normalize_phone(order.phone),
            "addressId": str(address["id"]),
        }
        data = self._request("POST", "/clients", payload=payload, use_counterparty_token=True)
        if isinstance(data, dict) and data.get("uuid"):
            return str(data["uuid"])
        logger.error("UkrPoshta create_recipient_client failed for order #%s: %s", order.pk, data)
        return None

    def create_shipment(self, order) -> str | None:
        """
        Create shipment via Ukrposhta and return barcode.
        Returns barcode string or None on failure.
        """
        if not self.is_configured:
            return None

        sender_uuid = getattr(settings, "UP_SENDER_CLIENT_UUID", "")
        if not sender_uuid:
            logger.warning("UkrPoshta: UP_SENDER_CLIENT_UUID not configured")
            return None

        recipient_uuid = self.create_recipient_client(order)
        if not recipient_uuid:
            return None

        weight_g = self._order_weight_g(order)
        declared = int(float(order.total))
        payload: dict = {
            "sender": {"uuid": sender_uuid},
            "recipient": {"uuid": recipient_uuid},
            "deliveryType": "W2W",
            "type": "EXPRESS",
            "paidByRecipient": True,
            "description": f"Замовлення #{order.pk}",
            "parcels": [
                {
                    "weight": weight_g,
                    "length": DEFAULT_PARCEL_LENGTH_CM,
                    "width": DEFAULT_PARCEL_WIDTH_CM,
                    "height": DEFAULT_PARCEL_HEIGHT_CM,
                    "declaredPrice": declared,
                }
            ],
        }
        if order.payment_method == "cod":
            payload["postPay"] = declared

        data = self._request("POST", "/shipments", payload=payload, use_counterparty_token=True)
        if not isinstance(data, dict):
            return None

        barcode = data.get("barcode") or data.get("shipmentGroupBarcode")
        if barcode:
            delivery_price = data.get("deliveryPrice")
            if delivery_price is not None and not order.delivery_cost:
                from apps.orders.models import Order

                Order.objects.filter(pk=order.pk).update(delivery_cost=Decimal(str(delivery_price)))
            logger.info("UkrPoshta shipment created: %s for order #%s", barcode, order.pk)
            return str(barcode)

        logger.error("UkrPoshta create_shipment failed for order #%s: %s", order.pk, data)
        return None

    def track(self, barcode: str) -> dict:
        """Return latest lifecycle status for a shipment."""
        data = self._request(
            "GET",
            f"/shipments/{barcode}/lifecycle",
            use_counterparty_token=True,
        )
        if isinstance(data, dict) and data.get("status"):
            return data

        statuses = self._request(
            "GET",
            f"/shipments/{barcode}/statuses",
            use_counterparty_token=True,
        )
        if isinstance(statuses, list) and statuses:
            return statuses[-1]
        if isinstance(statuses, dict):
            items = statuses.get("items") or statuses.get("data") or []
            if isinstance(items, list) and items:
                return items[-1]
        return {}

    def is_delivered(self, info: dict) -> bool:
        status = str(info.get("status") or info.get("eventName") or "").upper()
        return status in UP_DELIVERED_STATUSES or "DELIVERED" in status
