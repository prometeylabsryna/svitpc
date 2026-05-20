from django.db import models
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.fields import CKEditor5Field


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
