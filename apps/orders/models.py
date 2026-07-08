"""Order models."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class OrderStatus(models.Model):
    name = models.CharField(_("Назва"), max_length=100)
    name_en = models.CharField(_("Назва (EN)"), max_length=100, blank=True)
    color = models.CharField(_("Колір (HEX)"), max_length=10, default="#6b7280")
    sort_order = models.PositiveSmallIntegerField(default=0)
    notify_customer = models.BooleanField(_("Сповіщати клієнта"), default=False)
    is_completed = models.BooleanField(
        _("Завершений (нараховувати бонуси)"),
        default=False,
        help_text=_("Після переходу в цей статус нараховуються бонуси за замовлення"),
    )

    class Meta:
        verbose_name = _("Статус замовлення")
        verbose_name_plural = _("Статуси замовлень")
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return self.name


class Order(models.Model):
    PAYMENT_CARD = "card"
    PAYMENT_CASH_ON_DELIVERY = "cod"
    PAYMENT_GOOGLE_PAY = "google_pay"
    PAYMENT_APPLE_PAY = "apple_pay"
    PAYMENT_INSTALLMENT = "installment"
    PAYMENT_CHOICES = [
        (PAYMENT_CARD, _("Картка")),
        (PAYMENT_CASH_ON_DELIVERY, _("Післяплата")),
        (PAYMENT_GOOGLE_PAY, "Google Pay"),
        (PAYMENT_APPLE_PAY, "Apple Pay"),
        (PAYMENT_INSTALLMENT, _("Розстрочка")),
    ]

    DELIVERY_NP = "nova_poshta"
    DELIVERY_UP = "ukrposhta"
    DELIVERY_PICKUP = "pickup"
    DELIVERY_CHOICES = [
        (DELIVERY_NP, _("Нова Пошта")),
        (DELIVERY_UP, _("Укрпошта")),
        (DELIVERY_PICKUP, _("Самовивіз")),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders", verbose_name=_("Покупець"))
    status = models.ForeignKey(OrderStatus, on_delete=models.PROTECT, verbose_name=_("Статус"))

    # Customer info (for guests / snapshot)
    first_name = models.CharField(_("Ім'я"), max_length=100)
    last_name = models.CharField(_("Прізвище"), max_length=100)
    email = models.EmailField(_("Email"), blank=True)
    phone = models.CharField(_("Телефон"), max_length=20)

    # Delivery
    delivery_type = models.CharField(_("Доставка"), max_length=20, choices=DELIVERY_CHOICES, default=DELIVERY_NP)
    city = models.CharField(_("Місто"), max_length=150, blank=True)
    city_ref = models.CharField(_("НП ref міста"), max_length=50, blank=True)
    warehouse = models.CharField(_("Відділення"), max_length=255, blank=True)
    warehouse_ref = models.CharField(_("НП ref відділення"), max_length=50, blank=True)

    # Payment
    payment_method = models.CharField(_("Оплата"), max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_CARD)
    is_paid = models.BooleanField(_("Оплачено"), default=False)
    payment_id = models.CharField(_("ID транзакції"), max_length=255, blank=True)

    # Totals
    total = models.DecimalField(_("Сума"), max_digits=12, decimal_places=2)
    delivery_cost = models.DecimalField(_("Доставка"), max_digits=8, decimal_places=2, default=0)
    discount = models.DecimalField(_("Знижка"), max_digits=10, decimal_places=2, default=0)
    bonus_used = models.DecimalField(_("Бонусів використано"), max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey(
        "loyalty.Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name=_("Промокод"),
    )
    comment = models.TextField(_("Коментар"), blank=True)

    # Delivery identifiers
    ttn = models.CharField(_("ТТН (НП)"), max_length=100, blank=True)
    up_barcode = models.CharField(_("Штрихкод УкрПошти"), max_length=100, blank=True)
    shipping_error = models.CharField(
        _("Помилка створення відправлення"),
        max_length=500,
        blank=True,
        help_text=_("Остання помилка API перевізника при створенні ТТН; очищається при успіху."),
    )
    postcode = models.CharField(_("Індекс (УкрПошта)"), max_length=10, blank=True)

    # Fiscalization
    fiscal_check_url = models.URLField(_("Чек"), blank=True)

    created_at = models.DateTimeField(_("Дата"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Замовлення")
        verbose_name_plural = _("Замовлення")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"#{self.pk} {self.first_name} {self.last_name}"

    def get_absolute_url(self) -> str:
        from django.urls import reverse
        return reverse("orders:detail", kwargs={"pk": self.pk})

    @property
    def payable_amount(self) -> Decimal:
        """Сума до оплати (товари після знижок/бонусів + доставка)."""
        return (self.total + self.delivery_cost).quantize(Decimal("0.01"))


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name=_("Замовлення"))
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Товар"))
    name = models.CharField(_("Назва товару"), max_length=500)
    sku = models.CharField(_("Артикул"), max_length=100, blank=True)
    price = models.DecimalField(_("Ціна"), max_digits=12, decimal_places=2)
    qty = models.PositiveSmallIntegerField(_("Кількість"), default=1)

    class Meta:
        verbose_name = _("Позиція")
        verbose_name_plural = _("Позиції")

    @property
    def subtotal(self):
        return self.price * self.qty


class OrderHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history", verbose_name=_("Замовлення"))
    status = models.ForeignKey(OrderStatus, on_delete=models.PROTECT, verbose_name=_("Статус"))
    comment = models.TextField(_("Коментар"), blank=True)
    notify_customer = models.BooleanField(_("Сповіщено клієнта"), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Запис статусу")
        ordering = ["-created_at"]
