"""Monobank (Mono Parts installment) provider."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import Decimal

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class MonobankProvider:
    INVOICE_URL = "https://api.monobank.ua/api/merchant/invoice/create"
    WEBHOOK_SECRET_HEADER = "X-Sign"

    def create_payment(self, order) -> dict:
        token = getattr(settings, "MONOBANK_TOKEN", "")
        if not token:
            logger.warning("Monobank: MONOBANK_TOKEN not configured")
            return {"url": "#", "fields": {}}

        # Mono Parts: paymentScheme "monoparts" for installments, "payment" for regular
        is_installment = getattr(order, "payment_method", "") == "monobank_parts"
        amount_kopiiky = int(order.payable_amount * 100)

        merchant_info = {
            "reference": str(order.pk),
            "destination": f"Замовлення #{order.pk}",
        }

        basket_order = [
            {
                "name": item.name,
                "qty": item.qty,
                "sum": int(Decimal(str(item.price)) * 100 * item.qty),
                "icon": "",
                "unit": "шт.",
                "code": str(getattr(item, "sku", item.pk) or item.pk),
            }
            for item in order.items.all()
        ]

        payload = {
            "amount": amount_kopiiky,
            "ccy": 980,  # UAH
            "merchantPaymInfo": {
                **merchant_info,
                "basketOrder": basket_order,
            },
            "redirectUrl": f"{settings.SITE_URL}/checkout/success/{order.pk}/",
            "webHookUrl": f"{settings.SITE_URL}/webhooks/monobank/",
            "paymentType": "debit",
        }
        if is_installment:
            payload["paymentType"] = "mono_parts"

        try:
            resp = httpx.post(
                self.INVOICE_URL,
                json=payload,
                headers={"X-Token": token, "Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return {"url": data.get("pageUrl", "#"), "invoice_id": data.get("invoiceId", "")}
        except Exception as exc:
            logger.error("Monobank create_payment failed for order #%s: %s", order.pk, exc)
            return {"url": "#", "fields": {}}

    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify Monobank webhook HMAC-SHA256 signature."""
        token = getattr(settings, "MONOBANK_TOKEN", "")
        if not token:
            return False
        expected = hmac.new(token.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def handle_webhook(self, body: bytes) -> None:
        from apps.orders.models import Order
        from apps.integrations.payments.signals import payment_completed

        try:
            data = json.loads(body)
            invoice_id = data.get("invoiceId", "")
            status = data.get("status", "")
            reference = (data.get("reference") or "")

            if not reference.isdigit():
                return
            order_pk = int(reference)

            try:
                order = Order.objects.get(pk=order_pk)
            except Order.DoesNotExist:
                return

            if status in ("success", "processing"):
                order.is_paid = True
                order.save(update_fields=["is_paid"])
                logger.info("Monobank invoice %s paid, order #%s", invoice_id, order_pk)
        except Exception as exc:
            logger.error("Monobank webhook error: %s", exc)
