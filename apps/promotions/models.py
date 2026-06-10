from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Promotion(models.Model):
    product = models.ForeignKey(
        "catalog.Product",
        verbose_name=_("Товар"),
        related_name="promotions",
        on_delete=models.CASCADE,
    )
    title_uk = models.CharField(
        _("Підзаголовок акції"),
        max_length=200,
        blank=True,
        default="",
        help_text=_(
            "Необов'язково. Наприклад: «Знижки до Дня Матері». "
            "Не пишіть «Акція» — це слово вже показується на значку товару."
        ),
    )
    title_en = models.CharField(_("Підзаголовок акції (EN)"), max_length=200, blank=True, default="")
    description_uk = models.TextField(_("Опис"), blank=True)
    description_en = models.TextField(_("Опис (EN)"), blank=True)
    auto_synced = models.BooleanField(
        _("Авто-синхронізовано"),
        default=False,
        help_text=_("Встановлено автоматично з поля «Кінець акції (таймер)» товару."),
    )
    start_date = models.DateTimeField(
        _("Початок"),
        help_text=_("Дата і час, коли акція починається."),
    )
    end_date = models.DateTimeField(
        _("Кінець"),
        help_text=_("Дата завершення. Таймер показує залишок до цього моменту."),
    )
    is_active = models.BooleanField(
        _("Активна"),
        default=True,
        help_text=_("Якщо вимкнено — акція не показується незалежно від дат."),
    )

    class Meta:
        verbose_name = _("Акція")
        verbose_name_plural = _("Акції")
        ordering = ["-end_date"]

    def __str__(self) -> str:
        return self.title_uk or f"{_('Акція для')}: {self.product}"

    @property
    def is_running(self) -> bool:
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date

    @property
    def time_remaining(self) -> float:
        now = timezone.now()
        if now < self.end_date:
            return (self.end_date - now).total_seconds()
        return 0.0


class HomeAdSettings(models.Model):
    """Singleton: how many home banners are visible at once (1–4)."""

    visible_columns = models.PositiveSmallIntegerField(
        _("Кількість банерів у рядку"),
        default=4,
        choices=[(n, str(n)) for n in range(1, 5)],
        help_text=_(
            "Скільки рекламних зображень показувати одночасно на головній сторінці (десктоп)."
        ),
    )

    class Meta:
        verbose_name = _("Реклама на головній")
        verbose_name_plural = _("Реклама на головній")

    def save(self, *args, **kwargs) -> None:
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs) -> None:
        return

    @classmethod
    def load(cls) -> HomeAdSettings:
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"visible_columns": 4})
        return obj

    def __str__(self) -> str:
        return str(_("Реклама на головній"))


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
