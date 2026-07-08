"""LiqPay payment provider."""

import base64
import hashlib
import json
import logging
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)


class LiqPayProvider:
    URL = "https://www.liqpay.ua/api/3/checkout"

    def _sign(self, data_str: str) -> str:
        raw = settings.LIQPAY_PRIVATE_KEY + data_str + settings.LIQPAY_PRIVATE_KEY
        return base64.b64encode(hashlib.sha1(raw.encode()).digest()).decode()

    _PAYTYPE_MAP = {
        "google_pay": "gpay",
        "apple_pay": "apay",
        "card": "card",
        "installment": "liqpay_installment",
    }

    def _paytype(self, payment_method: str) -> str:
        """Map order payment_method to LiqPay paytype."""
        return self._PAYTYPE_MAP.get(payment_method, "card")

    def create_payment(self, order) -> dict:
        if not settings.LIQPAY_PUBLIC_KEY:
            return {"url": "#", "data": "", "signature": ""}
        server_url = getattr(settings, "LIQPAY_SERVER_URL", "") or f"{settings.SITE_URL}/webhooks/liqpay/"
        params = {
            "version": 3,
            "public_key": settings.LIQPAY_PUBLIC_KEY,
            "action": "pay",
            "paytype": self._paytype(order.payment_method),
            "amount": str(order.payable_amount),
            "currency": "UAH",
            "description": f"Замовлення #{order.pk}",
            "order_id": str(order.pk),
            "server_url": server_url,
            "result_url": f"{settings.SITE_URL}/checkout/success/{order.pk}/",
            "sandbox": 1 if getattr(settings, "LIQPAY_SANDBOX", False) else 0,
        }
        data = base64.b64encode(json.dumps(params).encode()).decode()
        signature = self._sign(data)
        return {"url": self.URL, "data": data, "signature": signature}

    def handle_webhook(self, post_data: dict) -> None:
        from apps.payments.services import apply_payment_event

        data_b64 = post_data.get("data", "")
        sig = post_data.get("signature", "")
        if self._sign(data_b64) != sig:
            logger.warning("LiqPay: invalid signature")
            return
        try:
            decoded = json.loads(base64.b64decode(data_b64).decode())
            order_id = int(decoded.get("order_id", 0))
            status = decoded.get("status", "")
            payment_id = str(decoded.get("payment_id", ""))

            if status not in ("success", "sandbox", "failure", "error", "reversed"):
                return  # проміжні статуси (wait_accept тощо) не записуємо

            apply_payment_event(
                order_id=order_id,
                provider="liqpay",
                idempotency_key=f"liqpay_{payment_id}_{status}",
                succeeded=status in ("success", "sandbox"),
                amount=Decimal(str(decoded.get("amount", 0))),
                transaction_id=payment_id,
                raw_response=decoded,
            )
        except Exception as exc:
            logger.error("LiqPay webhook error: %s", exc)
