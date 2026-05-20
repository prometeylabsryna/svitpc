"""Reviews and ratings for products."""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Review(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="reviews", verbose_name=_("Товар"))
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews", verbose_name=_("Покупець"))
    author_name = models.CharField(_("Ім'я"), max_length=100)
    rating = models.PositiveSmallIntegerField(_("Оцінка"), validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(_("Відгук"))
    is_approved = models.BooleanField(_("Схвалено"), default=False)
    created_at = models.DateTimeField(_("Дата"), auto_now_add=True)

    class Meta:
        verbose_name = _("Відгук")
        verbose_name_plural = _("Відгуки")
        ordering = ["-created_at"]
        unique_together = [("product", "customer")]

    def __str__(self) -> str:
        return f"{self.author_name} → {self.product.name} ({self.rating}★)"
