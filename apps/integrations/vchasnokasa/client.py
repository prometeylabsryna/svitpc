"""Vchasno.Kasa fiscal receipt client — https://kasa.vchasno.ua"""

from __future__ import annotations

import logging
from decimal import Decimal

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://kasa.vchasno.ua"
FISCAL_EXECUTE_URL = f"{BASE_URL}/api/v2/fiscal/execute"

# Vchasno payment type codes (integration docs).
PAY_CASH = 0
PAY_CASHLESS = 1


class VchasnoKasaClient:
    """Fiscal receipt creation via Vchasno.Kasa API v2."""

    def __init__(self) -> None:
        self._token = getattr(settings, "VCHASNO_CASHBOX_KEY", "")
        self._device = getattr(settings, "VCHASNO_DEVICE_NAME", "SvitPC")
        self._taxgrp = int(getattr(settings, "VCHASNO_TAX_GRP", 1))

    def is_configured(self) -> bool:
        return bool(self._token)

    def create_receipt(self, order) -> str | None:
        """
        Create fiscal receipt for the given order.
        Returns the receipt URL or None on failure.
        """
        if not self.is_configured():
            logger.info("Vchasno: token not configured, skipping receipt for order #%s", order.pk)
            return None

        payload = self._build_payload(order)

        try:
            resp = httpx.post(
                FISCAL_EXECUTE_URL,
                json=payload,
                headers={
                    "Authorization": self._token,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("Vchasno create_receipt HTTP error for order #%s: %s", order.pk, exc)
            return None

        if data.get("res") != 0:
            logger.error(
                "Vchasno fiscal error for order #%s: res=%s %s",
                order.pk,
                data.get("res"),
                data.get("errortxt") or data,
            )
            return None

        info = data.get("info") or {}
        url = info.get("qr") or info.get("url")
        if url:
            logger.info("Vchasno receipt created: %s for order #%s", url, order.pk)
        else:
            logger.warning("Vchasno: receipt created but no URL in response for order #%s", order.pk)
        return url

    def ping(self) -> bool:
        """Check token validity via shift status request (task 18)."""
        if not self.is_configured():
            return False
        try:
            resp = httpx.post(
                FISCAL_EXECUTE_URL,
                json={
                    "ver": 6,
                    "source": "API",
                    "device": self._device,
                    "tag": "ping",
                    "type": 1,
                    "fiscal": {"task": 18},
                },
                headers={
                    "Authorization": self._token,
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("res") == 0
        except Exception as exc:
            logger.error("Vchasno ping error: %s", exc)
            return False

    def _build_payload(self, order) -> dict:
        rows = self._build_rows(order)
        payable = order.payable_amount
        pay_type = PAY_CASH if order.payment_method == "cod" else PAY_CASHLESS

        return {
            "ver": 6,
            "source": "API",
            "device": self._device,
            "tag": str(order.pk),
            "type": 1,
            "fiscal": {
                "task": 1,
                "receipt": {
                    "sum": float(payable),
                    "rows": rows,
                    "pays": [{"type": pay_type, "sum": float(payable)}],
                    "comment_down": f"Замовлення #{order.pk}",
                },
            },
        }

    def _build_rows(self, order) -> list[dict]:
        items = list(order.items.all())
        goods_total = sum((item.price * item.qty for item in items), Decimal("0"))
        discount_left = max(Decimal("0"), goods_total - order.total)
        rows: list[dict] = []

        for item in items:
            row_total = item.price * item.qty
            row_disc = min(discount_left, row_total)
            discount_left -= row_disc
            rows.append(
                {
                    "code": item.sku or str(item.product_id or item.pk),
                    "name": item.name[:500],
                    "cnt": item.qty,
                    "disc": float(row_disc),
                    "price": float(item.price),
                    "taxgrp": self._taxgrp,
                }
            )

        if order.delivery_cost > 0:
            rows.append(
                {
                    "code": "delivery",
                    "name": "Доставка",
                    "cnt": 1,
                    "disc": 0,
                    "price": float(order.delivery_cost),
                    "taxgrp": self._taxgrp,
                }
            )

        return rows
