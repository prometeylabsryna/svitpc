from celery import shared_task

from django.conf import settings
from django.utils.translation import gettext as _

from .dispatch import notify_order_customer
from .service import send_notification


@shared_task
def notify_new_order(order_pk: int) -> None:
    from apps.orders.models import Order

    try:
        order = Order.objects.select_related("customer", "status").get(pk=order_pk)
    except Order.DoesNotExist:
        return

    notify_order_customer(
        order,
        "order_created",
        push_title=_("СвітПК — замовлення прийнято"),
        push_body=_("Замовлення №%(pk)s успішно оформлено") % {"pk": order.pk},
        push_tag=f"order-new-{order.pk}",
    )

    if settings.TELEGRAM_ADMIN_CHAT_ID:
        send_notification(
            "telegram",
            settings.TELEGRAM_ADMIN_CHAT_ID,
            "order_created_admin",
            {"order": order},
        )


@shared_task
def notify_order_status(order_pk: int) -> None:
    from apps.orders.models import Order

    try:
        order = Order.objects.select_related("customer", "status").get(pk=order_pk)
    except Order.DoesNotExist:
        return

    if not order.status.notify_customer:
        return

    notify_order_customer(
        order,
        "order_status_changed",
        push_title=_("СвітПК — статус замовлення"),
        push_body=_("Замовлення №%(pk)s: %(status)s")
        % {"pk": order.pk, "status": order.status.name},
        push_tag=f"order-status-{order.pk}",
    )


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
