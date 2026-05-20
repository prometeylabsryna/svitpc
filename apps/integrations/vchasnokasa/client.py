"""Vchasno.Kasa fiscal receipt client — https://vchasno.ua/"""

from __future__ import annotations

import logging
from decimal import Decimal

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)
BASE_URL = "https://api.vchasno.ua"


class VchasnoKasaClient:
    """Fiscal receipt creation via Vchasno.Kasa API."""

    PAY_CARD = "CASHLESS"
    PAY_CASH = "CASH"

    def __init__(self) -> None:
        self._login = getattr(settings, "VCHASNO_LOGIN", "")
        self._password = getattr(settings, "VCHASNO_PASSWORD", "")
        self._cashbox_key = getattr(settings, "VCHASNO_CASHBOX_KEY", "")

    def _get_token(self) -> str | None:
        if not self._login or not self._password:
            return None
        try:
            resp = httpx.post(
                f"{BASE_URL}/api/auth",
                json={"login": self._login, "password": self._password},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("token")
        except Exception as exc:
            logger.error("Vchasno auth error: %s", exc)
            return None

    def create_receipt(self, order) -> str | None:
        """
        Create fiscal receipt for the given order.
        Returns the receipt URL or None on failure.
        """
        if not self._login or not self._password or not self._cashbox_key:
            logger.info("Vchasno: credentials not configured, skipping receipt for order #%s", order.pk)
            return None

        token = self._get_token()
        if not token:
            return None

        pay_type = self.PAY_CASH if order.payment_method == "cod" else self.PAY_CARD
        tax_rate = getattr(settings, "VCHASNO_TAX_RATE", 20)  # % PDV

        goods = [
            {
                "name": item.name,
                "price": float(item.price),
                "quantity": item.qty,
                "unit": "шт",
                "letters": "А",  # VAT code
                "tax": [{"type": "VALUE_ADDED_TAX", "value": tax_rate, "included": True}],
            }
            for item in order.items.all()
        ]

        payload = {
            "cashbox_key": self._cashbox_key,
            "payment": {
                "type": pay_type,
                "value": float(order.total),
            },
            "goods": goods,
        }

        try:
            resp = httpx.post(
                f"{BASE_URL}/api/receipts",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            url = data.get("url") or data.get("receipt_url")
            if url:
                logger.info("Vchasno receipt created: %s for order #%s", url, order.pk)
            else:
                logger.warning("Vchasno: receipt created but no URL in response for order #%s", order.pk)
            return url
        except Exception as exc:
            logger.error("Vchasno create_receipt error for order #%s: %s", order.pk, exc)
            return None
