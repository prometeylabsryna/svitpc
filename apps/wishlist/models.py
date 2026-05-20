from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class WishlistItem(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist", verbose_name=_("Покупець"))
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, verbose_name=_("Товар"))
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Бажаний товар")
        verbose_name_plural = _("Список бажань")
        unique_together = [("customer", "product")]
        ordering = ["-added_at"]
