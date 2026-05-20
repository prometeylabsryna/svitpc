from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.fields import CKEditor5Field


class ServiceCategory(models.Model):
    name = models.CharField(_("Назва"), max_length=200)
    name_en = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("Категорія послуг")
        verbose_name_plural = _("Категорії послуг")
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return self.name


class Service(models.Model):
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(_("Назва"), max_length=255)
    name_en = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(unique=True)
    description = CKEditor5Field(_("Опис"), config_name="default", blank=True)
    description_en = CKEditor5Field(_("Опис (EN)"), config_name="default", blank=True)
    image = models.ImageField(_("Зображення"), upload_to="services/", null=True, blank=True)
    is_active = models.BooleanField(_("Активна"), default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = _("Послуга")
        verbose_name_plural = _("Послуги")
        ordering = ["category__sort_order", "sort_order"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        from django.urls import reverse
        return reverse("services:detail", kwargs={"slug": self.slug})


class PriceItem(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="prices")
    name = models.CharField(_("Позиція"), max_length=255)
    name_en = models.CharField(max_length=255, blank=True)
    price_from = models.DecimalField(_("Ціна від"), max_digits=10, decimal_places=2, null=True, blank=True)
    price_to = models.DecimalField(_("Ціна до"), max_digits=10, decimal_places=2, null=True, blank=True)
    price_text = models.CharField(_("Ціна (текст)"), max_length=100, blank=True, help_text="напр. «від 500 грн»")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("Прайс-позиція")
        ordering = ["sort_order"]


class ServiceRequest(models.Model):
    STATUS_NEW = "new"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_WAITING_PARTS = "waiting_parts"
    STATUS_READY = "ready"
    STATUS_DONE = "done"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_NEW, _("Нова")),
        (STATUS_IN_PROGRESS, _("В роботі")),
        (STATUS_WAITING_PARTS, _("Очікує запчастин")),
        (STATUS_READY, _("Готова до видачі")),
        (STATUS_DONE, _("Видана")),
        (STATUS_CANCELLED, _("Скасована")),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="service_requests", verbose_name=_("Клієнт"),
    )
    customer_name = models.CharField(_("Ім'я"), max_length=150)
    customer_phone = models.CharField(_("Телефон"), max_length=20)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Послуга"))
    device = models.CharField(_("Пристрій"), max_length=255)
    description = models.TextField(_("Опис несправності"))
    status = models.CharField(_("Статус"), max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)
    technician_notes = models.TextField(_("Примітки техніка"), blank=True)
    estimated_cost = models.DecimalField(_("Орієнтовна вартість"), max_digits=10, decimal_places=2, null=True, blank=True)
    final_cost = models.DecimalField(_("Фактична вартість"), max_digits=10, decimal_places=2, null=True, blank=True)
    telegram_chat_id = models.CharField(_("Telegram Chat ID"), max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Заявка сервісного центру")
        verbose_name_plural = _("Заявки сервісного центру")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"#{self.pk} {self.customer_name} — {self.device}"

    def get_status_display_uk(self) -> str:
        return dict(self.STATUS_CHOICES).get(self.status, self.status)
