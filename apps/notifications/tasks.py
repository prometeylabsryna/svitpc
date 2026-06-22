import logging

from celery import shared_task

from django.conf import settings
from django.utils.translation import gettext as _

from .dispatch import notify_order_customer, notify_site_owner, order_context
from .service import send_notification

logger = logging.getLogger(__name__)

# Isolated from Brain/catalog sync workers — see celery_worker_priority in docker-compose.
_NOTIFY_QUEUE = "priority"
_NOTIFY_TASK_OPTS = {
    "bind": True,
    "max_retries": 3,
    "default_retry_delay": 60,
    "queue": _NOTIFY_QUEUE,
}


def _load_new_order(order_pk: int):
    from apps.orders.models import Order

    try:
        return (
            Order.objects.select_related("customer", "status")
            .prefetch_related("items")
            .get(pk=order_pk)
        )
    except Order.DoesNotExist:
        return None


@shared_task(**_NOTIFY_TASK_OPTS)
def notify_new_order_owner(self, order_pk: int) -> None:
    """Email store owner — priority queue, retries on SMTP/Resend failures."""
    order = _load_new_order(order_pk)
    if order is None:
        return
    try:
        if notify_site_owner("order_created_admin", order_context(order)):
            return
    except Exception as exc:
        logger.exception("notify_new_order_owner failed order_pk=%s", order_pk)
        raise self.retry(exc=exc) from exc
    logger.warning("notify_new_order_owner: email not sent for order #%s, retrying", order_pk)
    raise self.retry()


@shared_task(**_NOTIFY_TASK_OPTS)
def notify_new_order_customer(self, order_pk: int) -> None:
    """Customer channels (email/SMS/push) — priority queue, isolated from catalog sync."""
    order = _load_new_order(order_pk)
    if order is None:
        return
    try:
        notify_order_customer(
            order,
            "order_created",
            push_title=_("СвітПК — замовлення прийнято"),
            push_body=_("Замовлення №%(pk)s успішно оформлено") % {"pk": order.pk},
            push_tag=f"order-new-{order.pk}",
        )
    except Exception as exc:
        logger.exception("notify_new_order_customer failed order_pk=%s", order_pk)
        raise self.retry(exc=exc) from exc


@shared_task
def notify_new_order(order_pk: int) -> None:
    """Backward-compatible wrapper (owner first, then customer)."""
    notify_new_order_owner.run(order_pk)
    notify_new_order_customer.run(order_pk)


@shared_task(**_NOTIFY_TASK_OPTS)
def notify_order_status(self, order_pk: int) -> None:
    from apps.orders.models import Order

    try:
        order = Order.objects.select_related("customer", "status").get(pk=order_pk)
    except Order.DoesNotExist:
        return

    if not order.status.notify_customer:
        return

    try:
        notify_order_customer(
            order,
            "order_status_changed",
            push_title=_("СвітПК — статус замовлення"),
            push_body=_("Замовлення №%(pk)s: %(status)s")
            % {"pk": order.pk, "status": order.status.name},
            push_tag=f"order-status-{order.pk}",
        )
    except Exception as exc:
        logger.exception("notify_order_status failed order_pk=%s", order_pk)
        raise self.retry(exc=exc) from exc


@shared_task
def notify_repair_status(request_pk: int) -> None:
    from django.conf import settings

    from apps.services.models import ServiceRequest

    try:
        req = ServiceRequest.objects.select_related("service").get(pk=request_pk)
    except ServiceRequest.DoesNotExist:
        return

    from apps.core.models import SiteSettings

    site = SiteSettings.load()
    ctx = {
        "req": req,
        "status_label": req.get_status_display_uk(),
        "site_phone": site.phone,
    }

    if req.telegram_chat_id:
        send_notification("telegram", req.telegram_chat_id, "repair_status_changed", ctx)

    if settings.TELEGRAM_ADMIN_CHAT_ID:
        send_notification(
            "telegram",
            settings.TELEGRAM_ADMIN_CHAT_ID,
            "repair_status_changed",
            ctx,
        )


@shared_task
def notify_promotion_push(promotion_pk: int) -> int:
    """Send web-push about a promotion to all subscribers. Returns number of users notified."""
    from apps.promotions.models import Promotion

    from .models import PushSubscription

    try:
        promo = Promotion.objects.get(pk=promotion_pk)
    except Promotion.DoesNotExist:
        return 0

    user_pks = list(PushSubscription.objects.values_list("customer_id", flat=True).distinct())
    if not user_pks:
        return 0

    count = 0
    for user_pk in user_pks:
        sent = send_notification("push", user_pk, "promotion", {
            "title": _("СвітПК — акція!"),
            "body": promo.title_uk or str(promo.product),
            "url": "/promotions/",
            "tag": f"promo-{promo.pk}",
        })
        if sent:
            count += 1
    return count
