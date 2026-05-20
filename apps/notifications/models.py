from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class PushSubscription(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(_("Endpoint"), max_length=500)
    p256dh = models.CharField(_("p256dh"), max_length=500)
    auth = models.CharField(_("auth"), max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Push-підписка")
