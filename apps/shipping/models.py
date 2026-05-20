from django.db import models
from django.utils.translation import gettext_lazy as _


class NovaPoshtaCity(models.Model):
    name = models.CharField(_("Місто"), max_length=200, db_index=True)
    name_en = models.CharField(max_length=200, blank=True)
    ref = models.CharField(_("Ref"), max_length=50, unique=True)
    area = models.CharField(_("Область"), max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Місто НП")
        verbose_name_plural = _("Міста НП")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class NovaPoshtaWarehouse(models.Model):
    city = models.ForeignKey(NovaPoshtaCity, on_delete=models.CASCADE, related_name="warehouses")
    name = models.CharField(_("Відділення"), max_length=300)
    ref = models.CharField(_("Ref"), max_length=50, unique=True)
    number = models.CharField(_("Номер"), max_length=20, blank=True)
    type = models.CharField(_("Тип"), max_length=50, blank=True)

    class Meta:
        verbose_name = _("Відділення НП")
        verbose_name_plural = _("Відділення НП")
        ordering = ["number"]

    def __str__(self) -> str:
        return f"{self.city.name}: {self.name}"
