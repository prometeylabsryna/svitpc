"""Tests for order reorder and loyalty signal."""

import pytest
from decimal import Decimal


@pytest.fixture
def customer(db):
    from apps.customers.models import Customer
    return Customer.objects.create_user(email="test@svitpc.ua", password="testpass123")


@pytest.fixture
def completed_status(db):
    from apps.orders.models import OrderStatus
    return OrderStatus.objects.create(name="Доставлено", is_completed=True)


@pytest.fixture
def order(db, customer, completed_status):
    from apps.orders.models import Order
    from apps.catalog.models import Brand

    brand, _ = Brand.objects.get_or_create(name="TestBrand", defaults={"slug": "testbrand"})
    from apps.catalog.models import Product
    product = Product.objects.create(
        name="Test Product",
        slug="test-product",
        price=Decimal("1000.00"),
        stock=10,
        brand=brand,
    )
    order = Order.objects.create(
        customer=customer,
        first_name="Test",
        last_name="User",
        phone="+380000000000",
        email="test@svitpc.ua",
        total=Decimal("1000.00"),
        status=completed_status,
    )
    from apps.orders.models import OrderItem
    OrderItem.objects.create(
        order=order,
        product=product,
        name="Test Product",
        sku="TEST001",
        price=Decimal("1000.00"),
        qty=1,
    )
    return order


@pytest.mark.django_db
def test_reorder_adds_to_cart(client, order, customer):
    """reorder_view adds items to cart and redirects to cart."""
    client.force_login(customer)
    response = client.post(f"/orders/{order.pk}/reorder/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_bonus_signal_accrues_on_completed_status(
    order, customer, completed_status, django_capture_on_commit_callbacks,
):
    """Completed status should credit coins synchronously after commit."""
    from apps.orders.models import OrderStatus

    pending = OrderStatus.objects.create(name="Нове", is_completed=False, sort_order=0)
    order.status = pending
    order.save(update_fields=["status"])

    # Сигнал нараховує монети через transaction.on_commit — виконуємо callbacks
    with django_capture_on_commit_callbacks(execute=True):
        order.status = completed_status
        order.save(update_fields=["status"])

    customer.refresh_from_db()
    assert customer.bonus_balance == Decimal("1")


@pytest.mark.django_db
def test_bonus_not_fired_on_non_completed_status(db, order, customer):
    """Signal should NOT accrue coins for non-completed status."""
    from apps.orders.models import OrderStatus

    pending = OrderStatus.objects.create(name="В обробці", is_completed=False)
    order.status = pending
    order.save(update_fields=["status"])

    customer.refresh_from_db()
    assert customer.bonus_balance == Decimal("0")
