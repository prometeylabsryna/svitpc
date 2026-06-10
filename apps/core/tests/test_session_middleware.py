from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.core.session_middleware import is_admin_request, session_cookie_name


def _login_form_csrf_token(html: str) -> str:
    match = re.search(
        r'auth-form__form.*?name="csrfmiddlewaretoken" value="([^"]+)"',
        html,
        re.DOTALL,
    )
    assert match, "login form CSRF token not found"
    return match.group(1)

User = get_user_model()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/admin/login/", True),
        ("/admin/", True),
        ("/en/admin/login/", True),
        ("/account/login/", False),
        ("/", False),
        ("/catalog/", False),
    ],
)
def test_is_admin_request(path: str, expected: bool) -> None:
    class _Request:
        path_info = path

    assert is_admin_request(_Request()) is expected


def test_session_cookie_name_differs_for_admin_and_storefront() -> None:
    class _AdminRequest:
        path_info = "/admin/"

    class _SiteRequest:
        path_info = "/account/login/"

    assert session_cookie_name(_AdminRequest()) == "admin_sessionid"
    assert session_cookie_name(_SiteRequest()) == "sessionid"


@pytest.mark.django_db
def test_admin_login_does_not_authenticate_storefront() -> None:
    User.objects.create_superuser("staff@svitpc.ua", "secret-pass-123")
    client = Client()

    login_page = client.get("/admin/login/")
    admin_login = client.post(
        "/admin/login/",
        {"username": "staff@svitpc.ua", "password": "secret-pass-123"},
        follow=True,
    )
    assert admin_login.status_code == 200

    admin_response = client.get("/admin/")
    assert admin_response.status_code == 200

    site_response = client.get("/account/")
    assert site_response.status_code == 302
    assert "/account/login/" in site_response["Location"]


@pytest.mark.django_db
def test_storefront_login_does_not_authenticate_admin() -> None:
    user = User.objects.create_user("shopper@example.com", "secret-pass-123")
    client = Client()

    login_page = client.get("/account/login/")
    assert login_page.status_code == 200

    response = client.post(
        "/account/login/",
        {"username": user.email, "password": "secret-pass-123"},
    )
    assert response.status_code == 302

    dashboard = client.get("/account/")
    assert dashboard.status_code == 200

    admin_response = client.get("/admin/")
    assert admin_response.status_code == 302
    assert "/admin/login/" in admin_response["Location"]


@pytest.mark.django_db
def test_storefront_login_csrf_ignores_stale_csrftoken_cookie(customer_factory) -> None:
    """Admin/other tabs must not break storefront login via a shared csrftoken cookie."""
    user = customer_factory(email="shopper@example.com", password="secret-pass-123")
    client = Client(enforce_csrf_checks=True)

    login_page = client.get("/account/login/")
    token = _login_form_csrf_token(login_page.content.decode())

    client.get("/admin/login/")
    client.cookies["csrftoken"] = "stale-admin-csrf-token"

    response = client.post(
        "/account/login/",
        {
            "username": user.email,
            "password": "secret-pass-123",
            "csrfmiddlewaretoken": token,
        },
    )
    assert response.status_code == 302
