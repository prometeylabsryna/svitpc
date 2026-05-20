from django.db import models
from django.utils.translation import gettext_lazy as _


class Promotion(models.Model):
    name = models.CharField(_("Назва"), max_length=255)
    name_en = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(_("Опис"), blank=True)
    description_en = models.TextField(blank=True)
    image = models.ImageField(_("Зображення"), upload_to="promotions/", null=True, blank=True)
    is_active = models.BooleanField(_("Активна"), default=True)
    date_start = models.DateTimeField(_("Початок"), null=True, blank=True)
    date_end = models.DateTimeField(_("Кінець"), null=True, blank=True)
    products = models.ManyToManyField("catalog.Product", related_name="promotions", blank=True, verbose_name=_("Товари"))
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("Акція")
        verbose_name_plural = _("Акції")
        ordering = ["-date_start", "sort_order"]

    def __str__(self) -> str:
        return self.name


class Banner(models.Model):
    POSITION_HOME = "home"
    POSITION_CATEGORY = "category"
    POSITION_CHOICES = [(POSITION_HOME, _("Головна")), (POSITION_CATEGORY, _("Каталог"))]

    title = models.CharField(_("Заголовок"), max_length=255, blank=True)
    image = models.ImageField(_("Зображення"), upload_to="banners/")
    image_mobile = models.ImageField(_("Зображення (mobile)"), upload_to="banners/mobile/", null=True, blank=True)
    link = models.URLField(_("Посилання"), blank=True)
    position = models.CharField(_("Позиція"), max_length=20, choices=POSITION_CHOICES, default=POSITION_HOME)
    is_active = models.BooleanField(_("Активний"), default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    date_start = models.DateTimeField(null=True, blank=True)
    date_end = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Банер")
        verbose_name_plural = _("Банери")
        ordering = ["sort_order"]

    def __str__(self) -> str:
        return self.title or f"Banner {self.pk}"
