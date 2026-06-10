"""Review submission access control tests."""

import pytest
from django.urls import reverse

from apps.catalog.models import Product
from apps.customers.models import Customer
from apps.reviews.models import Review
from apps.reviews.utils import product_review_return_url


@pytest.fixture
def product(db) -> Product:
    return Product.objects.create(name="Тестовий товар", slug="test-review-product", price=100)


@pytest.fixture
def customer(db) -> Customer:
    return Customer.objects.create_user(
        email="reviewer@svitpc.ua",
        password="Str0ngPass!",
        first_name="Олег",
    )


@pytest.mark.django_db
def test_guest_sees_register_cta(client, product: Product) -> None:
    response = client.get(reverse("reviews:product", args=[product.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Зареєструватись" in content
    assert 'name="author_name"' not in content
    assert f"/product/{product.slug}/%23reviews" in content or f"/product/{product.slug}/#reviews" in content


@pytest.mark.django_db
def test_review_return_url_includes_reviews_hash(rf, product: Product) -> None:
    request = rf.get("/product/test/")
    assert product_review_return_url(request, product) == f"/product/{product.slug}/#reviews"


@pytest.mark.django_db
def test_authenticated_user_sees_review_form(client, product: Product, customer: Customer) -> None:
    client.force_login(customer)
    response = client.get(reverse("reviews:product", args=[product.pk]))
    assert response.status_code == 200
    assert b'name="author_name"' in response.content


@pytest.mark.django_db
def test_guest_cannot_submit_review(client, product: Product) -> None:
    response = client.post(
        reverse("reviews:submit", args=[product.pk]),
        {
            "author_name": "Гість",
            "rating": "5",
            "text": "Фейковий відгук",
        },
    )
    assert response.status_code == 200
    assert Review.objects.count() == 0
    assert "review-form__error" in response.content.decode()


@pytest.mark.django_db
def test_authenticated_user_can_submit_review(client, product: Product, customer: Customer) -> None:
    client.force_login(customer)
    response = client.post(
        reverse("reviews:submit", args=[product.pk]),
        {
            "author_name": "Олег",
            "rating": "4",
            "text": "Гарний товар",
        },
    )
    assert response.status_code == 200
    review = Review.objects.get(product=product, customer=customer)
    assert review.rating == 4
    assert review.text == "Гарний товар"
    assert review.is_approved is False
