from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class BonusTransaction(models.Model):
    TYPE_EARN = "earn"
    TYPE_SPEND = "spend"
    TYPE_ADJUST = "adjust"
    TYPE_BIRTHDAY = "birthday"
    TYPE_CHOICES = [
        (TYPE_EARN, _("Нарахування")),
        (TYPE_SPEND, _("Списання")),
        (TYPE_ADJUST, _("Коригування")),
        (TYPE_BIRTHDAY, _("Бонус ДН")),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bonus_transactions")
    order = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(_("Сума"), max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(_("Баланс після"), max_digits=10, decimal_places=2)
    description = models.CharField(_("Опис"), max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Бонусна транзакція")
        verbose_name_plural = _("Бонусні транзакції")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_transaction_type_display()} {self.amount} — {self.customer}"


class Coupon(models.Model):
    code = models.CharField(_("Код"), max_length=50, unique=True, db_index=True)
    discount_type = models.CharField(_("Тип"), max_length=10, choices=[("percent", _("Відсоток")), ("fixed", _("Фіксована сума"))], default="percent")
    discount_value = models.DecimalField(_("Знижка"), max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(_("Мін. замовлення"), max_digits=10, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(_("Макс. використань"), default=0, help_text=_("0 = необмежено"))
    used_count = models.PositiveIntegerField(_("Використано"), default=0)
    valid_from = models.DateTimeField(_("Дійсний з"), null=True, blank=True)
    valid_to = models.DateTimeField(_("Дійсний до"), null=True, blank=True)
    is_active = models.BooleanField(_("Активний"), default=True)

    class Meta:
        verbose_name = _("Промокод")
        verbose_name_plural = _("Промокоди")

    def __str__(self) -> str:
        return self.code
