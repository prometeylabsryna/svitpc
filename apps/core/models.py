"""Core models — site-wide settings singleton."""

from __future__ import annotations

from django.core.cache import cache
from django.db import models
from django.utils.translation import gettext_lazy as _

SITE_SETTINGS_CACHE_KEY = "core.site_settings"


class SiteSettings(models.Model):
    """Singleton: store contacts and branding shown across the site."""

    name = models.CharField(_("Назва магазину"), max_length=120, default="СвітПК")
    name_en = models.CharField(_("Назва (EN)"), max_length=120, blank=True)
    phone = models.CharField(
        _("Телефон"),
        max_length=40,
        default="+38 (044) 000-00-00",
        help_text=_("Відображається у футері, на сторінці контактів та в листах."),
    )
    email = models.EmailField(_("Email"), max_length=254, default="info@svitpc.ua")
    viber_phone = models.CharField(
        _("Viber (телефон)"),
        max_length=40,
        blank=True,
        help_text=_(
            "Номер для чату у Viber. Якщо порожньо — використовується основний телефон."
        ),
    )
    tagline = models.TextField(
        _("Короткий опис у футері"),
        blank=True,
        help_text=_("Якщо порожньо — використовується стандартний текст перекладу."),
    )
    tagline_en = models.TextField(_("Короткий опис у футері (EN)"), blank=True)
    address = models.CharField(_("Адреса"), max_length=255, blank=True)
    legal_entity = models.CharField(
        _("Форма суб'єкта"),
        max_length=20,
        blank=True,
        default="ФОП",
        help_text=_("Напр.: ФОП або ТОВ — для блоку юридичної інформації на сайті."),
    )
    legal_name = models.CharField(
        _("ПІБ / назва юрособи"),
        max_length=255,
        blank=True,
        help_text=_("Як у документах для LiqPay та податкової (ПІБ ФОП або повна назва ТОВ)."),
    )
    tax_id = models.CharField(
        _("РНОКПП / ЄДРПОУ"),
        max_length=20,
        blank=True,
        help_text=_("ІПН для ФОП або ЄДРПОУ для ТОВ."),
    )
    legal_address = models.CharField(
        _("Юридична адреса"),
        max_length=500,
        blank=True,
        help_text=_("Адреса реєстрації з податкової або виписки."),
    )
    facebook_url = models.URLField(_("Facebook"), blank=True)
    instagram_url = models.URLField(_("Instagram"), blank=True)
    telegram_url = models.URLField(
        _("Telegram (посилання)"),
        blank=True,
        help_text=_("Посилання на канал або бот для футера (не плутати з TELEGRAM_BOT_LINK у .env)."),
    )
    used_category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Категорія Б/У"),
        help_text=_("Розділ каталогу для вживаної техніки. Зазвичай «Б/У»."),
    )
    show_used_category = models.BooleanField(
        _("Показувати розділ Б/У на сайті"),
        default=True,
        help_text=_("Вимкніть, щоб приховати категорію з меню та закрити її сторінки."),
    )

    class Meta:
        verbose_name = _("Налаштування сайту")
        verbose_name_plural = _("Налаштування сайту")

    def save(self, *args, **kwargs) -> None:
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(SITE_SETTINGS_CACHE_KEY)
        from apps.catalog.nav import invalidate_nav_cache
        from apps.core.used_category import invalidate_hidden_used_category_cache

        invalidate_nav_cache()
        invalidate_hidden_used_category_cache()

    def delete(self, *args, **kwargs) -> None:
        return

    @classmethod
    def load(cls) -> SiteSettings:
        cached = cache.get(SITE_SETTINGS_CACHE_KEY)
        if isinstance(cached, cls):
            return cached
        if cached is not None:
            try:
                return cls.objects.select_related("used_category").get(pk=cached)
            except cls.DoesNotExist:
                cache.delete(SITE_SETTINGS_CACHE_KEY)
        obj, _ = cls.objects.select_related("used_category").get_or_create(pk=1)
        cache.set(SITE_SETTINGS_CACHE_KEY, obj, timeout=None)
        return obj

    def has_legal_info(self) -> bool:
        return bool(str(self.legal_name or "").strip() and str(self.tax_id or "").strip())

    def effective_viber_phone(self) -> str:
        custom = str(self.viber_phone or "").strip()
        if custom:
            return custom
        return str(self.phone or "").strip()

    def localized(self, field: str, *, lang: str | None = None) -> str:
        from django.utils import translation

        code = (lang or translation.get_language() or "uk").split("-")[0].lower()
        if code == "en":
            en_val = getattr(self, f"{field}_en", "") or ""
            if str(en_val).strip():
                return str(en_val).strip()
        return str(getattr(self, field, "") or "").strip()

    def __str__(self) -> str:
        return str(self.name or _("Налаштування сайту"))
