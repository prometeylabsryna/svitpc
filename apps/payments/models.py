from django.db import models
from django.utils.translation import gettext_lazy as _


class Payment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"
    STATUS_CHOICES = [
        (STATUS_PENDING, _("Очікує")),
        (STATUS_SUCCESS, _("Успішно")),
        (STATUS_FAILED, _("Невдало")),
        (STATUS_REFUNDED, _("Повернуто")),
    ]

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(_("Провайдер"), max_length=30)  # liqpay, wayforpay, monobank
    status = models.CharField(_("Статус"), max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    amount = models.DecimalField(_("Сума"), max_digits=12, decimal_places=2)
    currency = models.CharField(_("Валюта"), max_length=5, default="UAH")
    transaction_id = models.CharField(_("ID транзакції"), max_length=255, blank=True)
    idempotency_key = models.CharField(
        _("Ключ ідемпотентності"),
        max_length=120,
        blank=True,
        null=True,
        unique=True,
        help_text="Format: liqpay_{payment_id}_{status}",
    )
    raw_response = models.JSONField(_("Відповідь провайдера"), default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Платіж")
        verbose_name_plural = _("Платежі")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.provider} #{self.transaction_id} {self.status}"
