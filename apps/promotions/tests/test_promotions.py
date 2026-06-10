from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.models import Product
from apps.catalog.services import get_sale_products_queryset
from apps.promotions.models import Promotion


@pytest.mark.django_db
class TestPromotionSignal:
    def test_sale_end_date_creates_auto_promotion(self, product_factory):
        product = product_factory(slug="timer-item", price=Decimal("500"))
        end = timezone.now() + timedelta(days=3)
        product.sale_end_date = end
        product.save(update_fields=["sale_end_date"])

        promo = Promotion.objects.get(product=product, auto_synced=True)
        assert promo.is_active is True
        assert promo.end_date == end
        assert promo.title_uk == ""

    def test_clear_sale_end_date_deactivates_auto_promotion(self, product_factory):
        product = product_factory(slug="clear-timer", price=Decimal("500"))
        product.sale_end_date = timezone.now() + timedelta(days=2)
        product.save(update_fields=["sale_end_date"])
        assert Promotion.objects.filter(product=product, auto_synced=True, is_active=True).exists()

        product.sale_end_date = None
        product.save(update_fields=["sale_end_date"])
        promo = Promotion.objects.get(product=product, auto_synced=True)
        assert promo.is_active is False

    def test_bulk_save_triggers_signal_per_product(self, product_factory):
        products = [
            product_factory(slug=f"bulk-{i}", price=Decimal("100"))
            for i in range(3)
        ]
        end = timezone.now() + timedelta(days=5)
        for product in products:
            product.sale_end_date = end
            product.save(update_fields=["sale_end_date"])

        assert Promotion.objects.filter(auto_synced=True, is_active=True).count() == 3


@pytest.mark.django_db
class TestPromotionModel:
    def test_is_running(self, product_factory):
        product = product_factory(slug="running", price=Decimal("500"))
        now = timezone.now()
        promo = Promotion.objects.create(
            product=product,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(days=1),
            is_active=True,
        )
        assert promo.is_running is True

    def test_manual_promotion_not_overwritten_by_signal(self, product_factory):
        product = product_factory(slug="manual", price=Decimal("500"))
        now = timezone.now()
        manual = Promotion.objects.create(
            product=product,
            title_uk="Літній розпродаж",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(days=10),
            is_active=True,
            auto_synced=False,
        )
        product.sale_end_date = now + timedelta(days=2)
        product.save(update_fields=["sale_end_date"])

        manual.refresh_from_db()
        assert manual.title_uk == "Літній розпродаж"
        assert manual.is_active is True
        assert Promotion.objects.filter(product=product, auto_synced=True, is_active=True).exists()


@pytest.mark.django_db
class TestPromotionsListView:
    def test_shows_running_promotions_only(self, client, product_factory):
        product = product_factory(slug="listed", price=Decimal("500"))
        now = timezone.now()
        Promotion.objects.create(
            product=product,
            title_uk="Знижка",
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(days=1),
            is_active=True,
        )
        Promotion.objects.create(
            product=product_factory(slug="future", price=Decimal("100")),
            title_uk="Майбутня",
            start_date=now + timedelta(days=2),
            end_date=now + timedelta(days=5),
            is_active=True,
        )

        response = client.get("/promotions/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "listed" in content or "Знижка" in content
        assert "Майбутня" not in content


@pytest.mark.django_db
class TestGetSaleProductsQueryset:
    def test_includes_discounted_products(self, product_factory):
        product_factory(
            slug="discounted",
            price=Decimal("800"),
            old_price=Decimal("1000"),
        )
        product_factory(slug="regular", price=Decimal("500"), old_price=None)

        pks = set(get_sale_products_queryset().values_list("pk", flat=True))
        assert Product.objects.get(slug="discounted").pk in pks
        assert Product.objects.get(slug="regular").pk not in pks

    def test_includes_running_promotion_products(self, product_factory):
        promoted = product_factory(slug="promo-item", price=Decimal("500"))
        product_factory(slug="plain", price=Decimal("500"))
        now = timezone.now()
        Promotion.objects.create(
            product=promoted,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(days=1),
            is_active=True,
        )

        pks = set(get_sale_products_queryset().values_list("pk", flat=True))
        assert promoted.pk in pks
        assert Product.objects.get(slug="plain").pk not in pks

    def test_excludes_inactive_promotion_products(self, product_factory):
        promoted = product_factory(slug="inactive-promo", price=Decimal("500"))
        now = timezone.now()
        Promotion.objects.create(
            product=promoted,
            start_date=now - timedelta(days=2),
            end_date=now - timedelta(days=1),
            is_active=True,
        )

        pks = set(get_sale_products_queryset().values_list("pk", flat=True))
        assert promoted.pk not in pks
