"""WayForPay payment provider."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)


class WayForPayProvider:
    URL = "https://secure.wayforpay.com/pay"
    API_URL = "https://api.wayforpay.com/api"

    def _sign(self, fields: list[str]) -> str:
        """HMAC-MD5 signature over joined fields."""
        secret = getattr(settings, "WAYFORPAY_SECRET_KEY", "")
        message = ";".join(str(f) for f in fields)
        return hmac.new(secret.encode(), message.encode(), hashlib.md5).hexdigest()

    def create_payment(self, order) -> dict:
        """Return fields dict for WayForPay hosted payment form."""
        merchant = getattr(settings, "WAYFORPAY_MERCHANT_ACCOUNT", "")
        site_url = getattr(settings, "SITE_URL", "http://localhost")
        default_domain = site_url.replace("https://", "").replace("http://", "")
        domain = getattr(settings, "WAYFORPAY_MERCHANT_DOMAIN", default_domain)
        if not merchant:
            logger.warning("WayForPay: WAYFORPAY_MERCHANT_ACCOUNT not configured")
            return {"url": self.URL, "fields": {}}

        order_ref = str(order.pk)
        order_date = int(time.time())
        amount = str(order.payable_amount)
        currency = "UAH"
        product_names = [item.name for item in order.items.all()]
        product_counts = [str(item.qty) for item in order.items.all()]
        product_prices = [str(item.price) for item in order.items.all()]

        # Signature fields per WayForPay docs
        sign_fields = [
            merchant, domain, order_ref, order_date, amount, currency,
            *product_names, *product_counts, *product_prices,
        ]
        signature = self._sign(sign_fields)

        fields = {
            "merchantAccount": merchant,
            "merchantDomainName": domain,
            "merchantTransactionSecureType": "AUTO",
            "orderReference": order_ref,
            "orderDate": order_date,
            "amount": amount,
            "currency": currency,
            "orderTimeout": 49000,
            "productName[]": product_names,
            "productCount[]": product_counts,
            "productPrice[]": product_prices,
            "clientFirstName": order.first_name,
            "clientLastName": order.last_name,
            "clientPhone": order.phone,
            "clientEmail": order.email,
            "merchantSignature": signature,
            "returnUrl": f"{settings.SITE_URL}/checkout/success/{order.pk}/",
            "serviceUrl": f"{settings.SITE_URL}/webhooks/wayforpay/",
            "language": "UA",
        }
        return {"url": self.URL, "fields": fields}

    def verify_signature(self, data: dict) -> bool:
        """Verify WayForPay webhook signature."""
        received_sig = data.get("merchantSignature", "")
        fields = [
            data.get("merchantAccount", ""),
            data.get("orderReference", ""),
            data.get("amount", ""),
            data.get("currency", ""),
            data.get("authCode", ""),
            data.get("cardPan", ""),
            data.get("transactionStatus", ""),
            data.get("reasonCode", ""),
        ]
        expected = self._sign(fields)
        return hmac.compare_digest(expected, received_sig)

    def handle_webhook(self, body: bytes) -> None:
        from decimal import Decimal

        from apps.payments.services import apply_payment_event

        try:
            data = json.loads(body)
        except Exception:
            return

        if not self.verify_signature(data):
            logger.warning("WayForPay: invalid webhook signature")
            return

        order_ref = str(data.get("orderReference", ""))
        if not order_ref.isdigit():
            return

        status = data.get("transactionStatus", "")
        if status not in ("Approved", "Captured", "Declined", "Expired", "Refunded"):
            return  # проміжні статуси (InProcessing, Pending) не записуємо

        tx_id = str(data.get("transactionId") or data.get("authCode") or "")
        try:
            amount = Decimal(str(data.get("amount", 0)))
        except Exception:
            amount = None

        apply_payment_event(
            order_id=int(order_ref),
            provider="wayforpay",
            idempotency_key=f"wayforpay_{order_ref}_{tx_id}_{status}",
            succeeded=status in ("Approved", "Captured"),
            amount=amount,
            transaction_id=tx_id,
            raw_response=data,
        )
