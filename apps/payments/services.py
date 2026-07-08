"""Єдиний шлях обробки платіжних подій для всіх провайдерів.

Всі webhook-и (LiqPay / WayForPay / Monobank) після перевірки підпису
викликають apply_payment_event() — атомарно, з ідемпотентністю через
Payment.idempotency_key та select_for_update на Order.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from apps.orders.models import Order

from .models import Payment

logger = logging.getLogger(__name__)


def apply_payment_event(
    *,
    order_id: int,
    provider: str,
    idempotency_key: str,
    succeeded: bool,
    amount: Decimal | None = None,
    transaction_id: str = "",
    raw_response: dict | None = None,
) -> bool:
    """Записати платіжну подію та (за успіху) позначити замовлення оплаченим.

    Повертає True, якщо подію оброблено; False — дубль або невідоме замовлення.
    Єдине місце в коді, де webhook змінює Order.is_paid.
    """
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id)
        except Order.DoesNotExist:
            logger.warning("%s webhook: order #%s not found", provider, order_id)
            return False

        # Ідемпотентність: подія з цим ключем вже оброблена
        if Payment.objects.filter(idempotency_key=idempotency_key).exists():
            return False

        Payment.objects.create(
            order=order,
            provider=provider,
            status=Payment.STATUS_SUCCESS if succeeded else Payment.STATUS_FAILED,
            amount=amount if amount is not None else order.payable_amount,
            transaction_id=transaction_id,
            idempotency_key=idempotency_key,
            raw_response=raw_response or {},
        )

        if succeeded and not order.is_paid:
            order.is_paid = True
            update_fields = ["is_paid"]
            if transaction_id:
                order.payment_id = transaction_id
                update_fields.append("payment_id")
            order.save(update_fields=update_fields)
            logger.info("%s: order #%s marked paid (tx=%s)", provider, order_id, transaction_id)

    return True
