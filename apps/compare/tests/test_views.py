import json

import pytest
from django.urls import reverse

from apps.catalog.models import Attribute, AttributeGroup, Filter, FilterGroup, Product, ProductAttribute, ProductFilter
from apps.compare.context_processors import compare_context
from apps.compare.views import COMPARE_KEY, _build_attr_groups


@pytest.mark.django_db
class TestBuildAttrGroups:
    def test_includes_filters_when_attribute_values_empty(self):
        fg = FilterGroup.objects.create(name="Производитель", sort_order=1)
        f = Filter.objects.create(group=fg, name="Grandstream", sort_order=1)
        ag = AttributeGroup.objects.create(name="Характеристики", sort_order=2)
        attr = Attribute.objects.create(group=ag, name="Аудиокодеки", sort_order=1)
        p1 = Product.objects.create(name="P1", slug="p1", price=100, sku="A1")
        p2 = Product.objects.create(name="P2", slug="p2", price=200, sku="A2")
        ProductFilter.objects.create(product=p1, filter=f)
        ProductFilter.objects.create(product=p2, filter=f)
        ProductAttribute.objects.create(product=p1, attribute=attr, value="")
        ProductAttribute.objects.create(product=p2, attribute=attr, value="")

        groups = _build_attr_groups([p1, p2])
        all_rows = [row for g in groups for row in g["rows"]]
        names = {row["name"] for row in all_rows}
        assert "Производитель" in names
        assert "Аудиокодеки" not in names
        producer = next(row for row in all_rows if row["name"] == "Производитель")
        assert producer["values"] == ["Grandstream", "Grandstream"]

    def test_includes_attributes_with_values(self):
        ag = AttributeGroup.objects.create(name="Загальні", sort_order=1)
        attr = Attribute.objects.create(group=ag, name="Потужність", sort_order=1)
        p = Product.objects.create(name="P", slug="p-power", price=50, sku="PWR")
        ProductAttribute.objects.create(product=p, attribute=attr, value="100 Вт")

        groups = _build_attr_groups([p])
        rows = [row for g in groups for row in g["rows"]]
        assert rows[0]["name"] == "Потужність"
        assert rows[0]["values"] == ["100 Вт"]


@pytest.mark.django_db
class TestCompareContext:
    def test_compare_count_from_session(self):
        from django.contrib.sessions.backends.db import SessionStore
        from django.test import RequestFactory

        store = SessionStore()
        store[COMPARE_KEY] = [1, 2, 3]
        store.save()
        req = RequestFactory().get("/")
        req.session = store
        assert compare_context(req)["compare_count"] == 3

    def test_compare_count_empty(self):
        from django.contrib.sessions.backends.db import SessionStore
        from django.test import RequestFactory

        req = RequestFactory().get("/")
        req.session = SessionStore()
        assert compare_context(req)["compare_count"] == 0


@pytest.mark.django_db
class TestCompareViews:
    def test_toggle_add_returns_parseable_hx_trigger(self, client):
        p = Product.objects.create(name="T", slug="t-compare-add", price=10, sku="TCA")
        url = reverse("compare:toggle", kwargs={"product_id": p.pk})
        response = client.post(url, HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["compareUpdated"] == 1
        assert trigger["compareActive"] is True
        assert client.session[COMPARE_KEY] == [p.pk]

    def test_toggle_remove_redirects_on_compare_page(self, client):
        p = Product.objects.create(name="T", slug="t-compare", price=10, sku="TC")
        session = client.session
        session[COMPARE_KEY] = [p.pk]
        session.save()

        url = reverse("compare:toggle", kwargs={"product_id": p.pk})
        response = client.post(
            url,
            HTTP_HX_REQUEST="true",
            HTTP_HX_CURRENT_URL="http://localhost:8001/compare/",
        )
        assert response.status_code == 204
        assert response["HX-Redirect"] == reverse("compare:page")
        trigger = json.loads(response["HX-Trigger"])
        assert trigger["compareUpdated"] == 0
        assert client.session[COMPARE_KEY] == []

    def test_clear_all(self, client):
        p = Product.objects.create(name="T2", slug="t2-compare", price=20, sku="TC2")
        session = client.session
        session[COMPARE_KEY] = [p.pk]
        session.save()

        response = client.post(
            reverse("compare:clear"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_CURRENT_URL="http://localhost:8001/compare/",
        )
        assert response.status_code == 204
        assert client.session[COMPARE_KEY] == []
