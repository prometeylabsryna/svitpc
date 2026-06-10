"""Authentication backends for Customer (email-based login)."""

from __future__ import annotations

from django.contrib.auth.backends import ModelBackend

from apps.customers.models import Customer

LOGIN_EMAIL_DOMAIN = "svitpc.ua"


class CustomerModelBackend(ModelBackend):
    """Allow staff login with full email or short name (e.g. admin → admin@svitpc.ua)."""

    def authenticate(
        self,
        request,
        username: str | None = None,
        password: str | None = None,
        **kwargs: object,
    ) -> Customer | None:
        if username is None:
            username = kwargs.get(Customer.USERNAME_FIELD)
        if username is None or password is None:
            return None

        login = str(username).strip()
        if "@" not in login:
            login = f"{login}@{LOGIN_EMAIL_DOMAIN}"

        try:
            user = Customer.objects.get(email__iexact=login)
        except Customer.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
