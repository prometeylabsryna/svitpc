"""Custom user model + address book for SvitPC customers."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class CustomerManager(BaseUserManager["Customer"]):
    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra: object,
    ) -> "Customer":
        if not email:
            raise ValueError(_("Email обов'язковий"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra: object) -> "Customer":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class Customer(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_("Email"), unique=True)
    first_name = models.CharField(_("Ім'я"), max_length=100, blank=True)
    last_name = models.CharField(_("Прізвище"), max_length=100, blank=True)
    phone = models.CharField(_("Телефон"), max_length=20, blank=True)
    birth_date = models.DateField(_("Дата народження"), null=True, blank=True)
    avatar = models.ImageField(_("Аватар"), upload_to="avatars/", null=True, blank=True)
    is_active = models.BooleanField(_("Активний"), default=True)
    is_staff = models.BooleanField(_("Персонал"), default=False)
    date_joined = models.DateTimeField(_("Дата реєстрації"), default=timezone.now)
    # Bonus system
    bonus_balance = models.DecimalField(_("Монети СвітПК"), max_digits=10, decimal_places=2, default=0)
    # Notifications consent
    consent_email = models.BooleanField(_("Email-розсилка"), default=True)
    consent_sms = models.BooleanField(_("SMS-розсилка"), default=True)
    # Web push subscription
    push_subscription_json = models.TextField(_("Push-підписка"), blank=True)
    # Messenger IDs for notifications
    telegram_chat_id = models.CharField(_("Telegram Chat ID"), max_length=50, blank=True)
    viber_id = models.CharField(_("Viber ID"), max_length=50, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects: CustomerManager = CustomerManager()  # type: ignore[assignment]

    class Meta:
        verbose_name = _("Покупець")
        verbose_name_plural = _("Покупці")
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.get_full_name() or self.email

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.first_name

    @property
    def is_birthday_today(self) -> bool:
        if not self.birth_date:
            return False
        today = timezone.localdate()
        return self.birth_date.month == today.month and self.birth_date.day == today.day


class Address(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses", verbose_name=_("Покупець"))
    label = models.CharField(_("Мітка"), max_length=50, blank=True, help_text=_("Наприклад: Дім, Робота"))
    first_name = models.CharField(_("Ім'я"), max_length=100)
    last_name = models.CharField(_("Прізвище"), max_length=100)
    phone = models.CharField(_("Телефон"), max_length=20)
    city = models.CharField(_("Місто"), max_length=150)
    city_ref = models.CharField(_("НП ref міста"), max_length=50, blank=True)
    delivery_type = models.CharField(
        _("Тип доставки"),
        max_length=20,
        choices=[
            ("nova_poshta", "Нова Пошта"),
            ("ukrposhta", "Укрпошта"),
            ("pickup", "Самовивіз"),
        ],
        default="nova_poshta",
    )
    warehouse = models.CharField(_("Відділення"), max_length=255, blank=True)
    warehouse_ref = models.CharField(_("НП ref відділення"), max_length=50, blank=True)
    is_default = models.BooleanField(_("За замовчуванням"), default=False)

    class Meta:
        verbose_name = _("Адреса")
        verbose_name_plural = _("Адреси")
        ordering = ["-is_default", "id"]

    def __str__(self) -> str:
        return f"{self.city}, {self.warehouse}"
