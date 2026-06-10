import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_birthday_greetings():
    """Daily: find customers with birthday today and send greeting + coupon."""
    import secrets
    import string
    from datetime import timedelta

    from django.utils import timezone

    from apps.customers.models import Customer
    from apps.loyalty.models import BonusTransaction, Coupon
    from apps.notifications.dispatch import notify_customer_channels, site_url

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
        if BonusTransaction.objects.filter(
            customer=customer,
            transaction_type=BonusTransaction.TYPE_BIRTHDAY,
            created_at__date=today,
        ).exists():
            continue

        code = _gen_code()
        while Coupon.objects.filter(code=code).exists():
            code = _gen_code()

        coupon = Coupon.objects.create(
            customer=customer,
            code=code,
            discount_type="percent",
            discount_value=10,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=30),
            max_uses=1,
            is_active=True,
            source=Coupon.SOURCE_BIRTHDAY,
        )

        ctx = {"customer": customer, "coupon": coupon, "site_url": site_url()}
        notify_customer_channels(customer, "birthday_greeting", ctx)

        BonusTransaction.objects.create(
            customer=customer,
            transaction_type=BonusTransaction.TYPE_BIRTHDAY,
            amount=0,
            balance_after=customer.bonus_balance,
            description=f"Привітання з днем народження {today}",
        )


@shared_task
def accrue_order_bonuses(order_pk: int):
    """Accrue SvitPC coins after order delivery."""
    from apps.orders.models import Order

    try:
        order = Order.objects.select_related("customer").get(pk=order_pk)
        from apps.loyalty.coins import accrue_coins_for_order

        accrue_coins_for_order(order)
    except Exception:
        logger.exception("accrue_order_bonuses failed for order_pk=%s", order_pk)


@shared_task
def expire_old_coins():
    """Daily: expire coins older than 6 months."""
    from apps.customers.models import Customer
    from apps.loyalty.coins import expire_customer_coins

    total = 0
    for customer in Customer.objects.filter(bonus_balance__gt=0).iterator():
        try:
            total += expire_customer_coins(customer)
        except Exception:
            logger.exception("expire_old_coins failed for customer_pk=%s", customer.pk)
    logger.info("expire_old_coins: expired %s coins total", total)
