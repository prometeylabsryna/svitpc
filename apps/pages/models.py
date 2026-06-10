from django.db import models
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.fields import CKEditor5Field


class ReturnRequest(models.Model):
    REASON_RETURN = "return"
    REASON_WARRANTY = "warranty"

    REASON_CHOICES = [
        (REASON_RETURN, _("Повернення")),
        (REASON_WARRANTY, _("Гарантія")),
    ]

    STATUS_NEW = "new"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_DONE = "done"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_NEW, _("Нова")),
        (STATUS_IN_PROGRESS, _("В обробці")),
        (STATUS_DONE, _("Завершена")),
        (STATUS_REJECTED, _("Відхилена")),
    ]

    full_name = models.CharField(_("ПІБ"), max_length=255)
    order_number = models.CharField(_("Номер замовлення"), max_length=64)
    phone = models.CharField(_("Телефон"), max_length=40)
    reason = models.CharField(
        _("Причина звернення"),
        max_length=20,
        choices=REASON_CHOICES,
    )
    description = models.TextField(_("Опис проблеми"), blank=True)
    photo = models.ImageField(
        _("Фото товару"),
        upload_to="returns/",
        blank=True,
        null=True,
    )
    status = models.CharField(
        _("Статус"),
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
    )
    created_at = models.DateTimeField(_("Створено"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Оновлено"), auto_now=True)

    class Meta:
        verbose_name = _("Заявка на повернення")
        verbose_name_plural = _("Заявки на повернення")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.full_name} — {self.order_number}"


class InfoPage(models.Model):
    SLUG_DELIVERY = "delivery"
    SLUG_PAYMENT = "payment"
    SLUG_WARRANTY = "warranty"
    SLUG_RETURNS = "returns"
    SLUG_CONTACT = "contact"
    SLUG_PRIVACY = "privacy"
    SLUG_FAQ = "faq"

    title = models.CharField(_("Заголовок"), max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(_("Slug"), unique=True)
    content = CKEditor5Field(_("Вміст"), config_name="default", blank=True)
    content_en = CKEditor5Field(_("Вміст (EN)"), config_name="default", blank=True)
    is_active = models.BooleanField(_("Активна"), default=True)
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Інфосторінка")
        verbose_name_plural = _("Інфосторінки")
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        from django.urls import reverse
        return reverse("pages:detail", kwargs={"slug": self.slug})
