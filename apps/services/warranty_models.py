"""Warranty / RMA registration models (Brain-style service claims)."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ProductSerial(models.Model):
    """Registry of sold product serial numbers for warranty lookup."""

    SOURCE_BRAIN = "brain"
    SOURCE_MANUAL = "manual"
    SOURCE_ORDER = "order"
    SOURCE_CHOICES = [
        (SOURCE_BRAIN, _("Brain API")),
        (SOURCE_MANUAL, _("Вручну")),
        (SOURCE_ORDER, _("Замовлення")),
    ]

    serial_number = models.CharField(_("Серійний номер"), max_length=128, unique=True, db_index=True)
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="serials",
        verbose_name=_("Товар"),
    )
    product_name = models.CharField(_("Назва товару"), max_length=500, blank=True)
    product_code = models.CharField(_("Код товару"), max_length=100, blank=True)
    articul = models.CharField(_("Артикул"), max_length=100, blank=True)
    sale_document = models.CharField(_("Документ продажу"), max_length=100, blank=True)
    sale_date = models.DateField(_("Дата продажу"), null=True, blank=True)
    warranty_until = models.DateField(_("Гарантія до"), null=True, blank=True)
    warranty_months = models.PositiveSmallIntegerField(_("Гарантія, міс"), null=True, blank=True)
    source = models.CharField(_("Джерело"), max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    brain_order_id = models.CharField(_("ID замовлення Brain"), max_length=50, blank=True)
    notes = models.TextField(_("Примітки"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Серійний номер")
        verbose_name_plural = _("Серійні номери")
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.serial_number


class WarrantyClaim(models.Model):
    """Warranty / RMA service request (оформлення гарантії)."""

    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_DONE = "done"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Чернетка")),
        (STATUS_SUBMITTED, _("Відправлена")),
        (STATUS_IN_PROGRESS, _("В обробці")),
        (STATUS_DONE, _("Завершена")),
        (STATUS_CANCELLED, _("Скасована")),
    ]

    DELIVERY_NOVA_POSHTA = "nova_poshta"
    DELIVERY_UKRPOSHTA = "ukrposhta"
    DELIVERY_OTHER = "other"
    DELIVERY_CHOICES = [
        (DELIVERY_NOVA_POSHTA, _("Нова Пошта")),
        (DELIVERY_UKRPOSHTA, _("Укрпошта")),
        (DELIVERY_OTHER, _("Інша")),
    ]

    rma_number = models.CharField(_("№ RMA"), max_length=20, blank=True, unique=True, db_index=True)
    serial_number = models.CharField(_("Серійний номер"), max_length=128, blank=True, db_index=True)
    without_serial_number = models.BooleanField(_("Без серійного номера"), default=False)
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warranty_claims",
        verbose_name=_("Товар"),
    )
    product_name = models.CharField(_("Товар"), max_length=500)
    product_code = models.CharField(_("Код товару"), max_length=100, blank=True)
    articul = models.CharField(_("Артикул"), max_length=100, blank=True)
    sale_document = models.CharField(_("Документ продажу"), max_length=100, blank=True)
    sale_date = models.DateField(_("Дата продажу"), null=True, blank=True)
    warranty_until = models.DateField(_("Гарантія до"), null=True, blank=True)
    is_under_warranty = models.BooleanField(_("Гарантійний"), null=True, blank=True)
    defect_description = models.CharField(_("Опис дефекту"), max_length=60)
    client_name = models.CharField(_("ПІБ клієнта"), max_length=200, blank=True)
    client_phone = models.CharField(_("Телефон клієнта"), max_length=20, blank=True)
    client_email = models.EmailField(_("Email клієнта"), blank=True)
    client_address = models.CharField(_("Адреса клієнта"), max_length=500, blank=True)
    delivery_service = models.CharField(
        _("Служба доставки"),
        max_length=20,
        choices=DELIVERY_CHOICES,
        blank=True,
    )
    waybill_number = models.CharField(_("Номер накладної СД"), max_length=100, blank=True)
    waybill_date = models.DateField(_("Дата накладної СД"), null=True, blank=True)
    comment = models.CharField(_("Коментар"), max_length=250, blank=True)
    status = models.CharField(
        _("Статус"),
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warranty_claims",
        verbose_name=_("Створив"),
    )
    product_serial = models.ForeignKey(
        ProductSerial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claims",
        verbose_name=_("Запис серійного номера"),
    )
    submitted_at = models.DateTimeField(_("Дата відправки"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Заявка на гарантію")
        verbose_name_plural = _("Заявки на гарантію")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        label = self.rma_number or f"#{self.pk}"
        return f"{label} — {self.product_name[:50]}"

    def assign_rma_number(self) -> None:
        if not self.rma_number and self.pk:
            self.rma_number = f"{self.pk:011d}"

    @property
    def warranty_status_label(self) -> str:
        if self.is_under_warranty is True:
            return str(_("Товар гарантійний"))
        if self.is_under_warranty is False:
            return str(_("Гарантія закінчилась"))
        return ""
