from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ChatSession(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(_("Ключ"), max_length=100, unique=True, db_index=True)
    telegram_chat_id = models.CharField(_("Telegram chat"), max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Чат-сесія")


class ChatMessage(models.Model):
    ROLE_CUSTOMER = "customer"
    ROLE_OPERATOR = "operator"
    ROLE_BOT = "bot"
    ROLE_CHOICES = [(ROLE_CUSTOMER, _("Клієнт")), (ROLE_OPERATOR, _("Оператор")), (ROLE_BOT, "Bot")]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_CUSTOMER)
    text = models.TextField(_("Повідомлення"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Повідомлення чату")
        ordering = ["created_at"]
