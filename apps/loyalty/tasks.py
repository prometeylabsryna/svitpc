import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_birthday_greetings():
    """Daily: find customers with birthday today, send greeting + coupon + SMS."""
    import secrets
    import string
    from datetime import timedelta

    from django.utils import timezone

    from apps.customers.models import Customer
    from apps.loyalty.models import BonusTransaction, Coupon
    from apps.notifications.service import send_notification

    today = timezone.localdate()
    customers = Customer.objects.filter(
        birth_date__month=today.month,
        birth_date__day=today.day,
        is_active=True,
    )

    def _gen_code() -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "BDAY-" + "".join(secrets.choice(alphabet) for _ in range(8))

    for customer in customers:
        # Generate birthday coupon (10% discount, valid 30 days)
        code = _gen_code()
        while Coupon.objects.filter(code=code).exists():
            code = _gen_code()

        coupon = Coupon.objects.create(
            code=code,
            discount_type="percent",
            discount_value=10,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=30),
            max_uses=1,
            is_active=True,
        )

        ctx = {"customer": customer, "coupon": coupon, "bonus_amount": 100}

        # Email
        send_notification(channel="email", recipient=customer.email, template_name="birthday_greeting", context=ctx)

        # SMS
        if getattr(customer, "phone", ""):
            send_notification(channel="sms", recipient=customer.phone, template_name="birthday_greeting", context=ctx)

        # Telegram
        tg_id = getattr(customer, "telegram_chat_id", "")
        if tg_id:
            send_notification(channel="telegram", recipient=tg_id, template_name="birthday_greeting", context=ctx)

        # Accrue 100 birthday bonuses
        customer.bonus_balance += 100
        customer.save(update_fields=["bonus_balance"])
        BonusTransaction.objects.create(
            customer=customer,
            transaction_type=BonusTransaction.TYPE_BIRTHDAY,
            amount=100,
            balance_after=customer.bonus_balance,
            description=f"Бонус на день народження {today}",
        )


@shared_task
def accrue_order_bonuses(order_pk: int):
    """Accrue loyalty bonuses after order delivery (2% of order total)."""
    from decimal import Decimal

    from apps.loyalty.models import BonusTransaction
    from apps.orders.models import Order

    try:
        order = Order.objects.select_related("customer").get(pk=order_pk)
        if not order.customer:
            return
        bonus = (order.total * Decimal("0.02")).quantize(Decimal("0.01"))
        if bonus <= 0:
            return
        order.customer.bonus_balance += bonus
        order.customer.save(update_fields=["bonus_balance"])
        BonusTransaction.objects.create(
            customer=order.customer,
            order=order,
            transaction_type=BonusTransaction.TYPE_EARN,
            amount=bonus,
            balance_after=order.customer.bonus_balance,
            description=f"Бонуси за замовлення #{order.pk} (2%)",
        )
    except Exception:
        logger.exception("accrue_order_bonuses failed for order_pk=%s", order_pk)
