"""Tests for reviews admin permissions."""

import pytest
from django.contrib import admin
from django.test import RequestFactory

from apps.reviews.admin import ReviewAdmin
from apps.reviews.models import Review


@pytest.fixture
def admin_request():
    request = RequestFactory().get("/admin/")
    request.user = type(
        "StaffUser",
        (),
        {"is_active": True, "is_staff": True, "is_superuser": False},
    )()
    return request


def test_review_admin_disallows_add(admin_request):
    assert ReviewAdmin(Review, admin.site).has_add_permission(admin_request) is False
