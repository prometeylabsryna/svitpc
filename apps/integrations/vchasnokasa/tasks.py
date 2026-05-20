from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fiscalize_payment(self, order_pk: int) -> None:
    """Create Vchasno.Kasa fiscal receipt for a paid order. Retries up to 3 times."""
    from apps.orders.models import Order
    from .client import VchasnoKasaClient

    try:
        order = Order.objects.get(pk=order_pk)
        if order.fiscal_check_url:
            logger.info("Order #%s already fiscalized, skipping.", order_pk)
            return
        client = VchasnoKasaClient()
        receipt_url = client.create_receipt(order)
        if receipt_url:
            Order.objects.filter(pk=order_pk).update(fiscal_check_url=receipt_url)
            logger.info("Fiscalization complete for order #%s: %s", order_pk, receipt_url)
        else:
            logger.warning("Fiscalization returned no URL for order #%s", order_pk)
    except Exception as exc:
        logger.error("Fiscalization failed for order #%s: %s", order_pk, exc)
        raise self.retry(exc=exc)
