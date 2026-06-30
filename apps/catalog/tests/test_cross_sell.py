import pytest

from apps.catalog.cross_sell import (
    primary_listing_category_pks,
    suggested_products_for_category,
    suggested_products_for_product,
)
from apps.catalog.models import Category

_IMAGE = "https://cdn.example.com/product.jpg"


def _ensure_branch(parent: Category | None, name: str, slug: str) -> Category:
    return Category.objects.create(name=name, slug=slug, parent=parent, is_active=True)


def _product(product_factory, **kwargs):
    kwargs.setdefault("image_url", _IMAGE)
    return product_factory(**kwargs)


@pytest.mark.django_db
class TestCrossSell:
    def test_laptop_shows_accessories_not_other_laptops(self, product_factory):
        root = _ensure_branch(None, "Ноутбуки, планшети", "ноутбуки-планшети")
        laptops = _ensure_branch(root, "Ноутбуки", "ноутбуки")
        accessories = _ensure_branch(root, "Аксесуари для ноутбуків", "аксесуари-для-ноутбуків")
        stands = _ensure_branch(accessories, "Підставки", "підставки-для-ноутбуків")

        laptop_a = _product(product_factory, name="Laptop A", slug="laptop-a")
        laptop_b = _product(product_factory, name="Laptop B", slug="laptop-b")
        stand = _product(product_factory, name="Stand Pro", slug="stand-pro")

        laptop_a.categories.add(laptops)
        laptop_b.categories.add(laptops)
        stand.categories.add(stands)

        picked, is_cross = suggested_products_for_product(laptop_a)
        assert is_cross is True
        assert stand in picked
        assert laptop_b not in picked

    def test_pc_shows_monitors_and_peripherals(self, product_factory):
        root = _ensure_branch(None, "Комп'ютери, аксесуари", "компютери-аксесуари")
        pcs = _ensure_branch(root, "Комп'ютери", "компютери")
        monitors_root = _ensure_branch(root, "Монітори та аксесуари", "монітори-та-аксесуари")
        monitors = _ensure_branch(monitors_root, "Монітори", "монітори")
        manipulators = _ensure_branch(root, "Маніпулятори", "маніпулятори")
        mice = _ensure_branch(manipulators, "Мишки", "мишки")

        pc = _product(product_factory, name="Desktop PC", slug="desktop-pc")
        other_pc = _product(product_factory, name="Other PC", slug="other-pc")
        monitor = _product(product_factory, name="Monitor 24", slug="monitor-24")
        mouse = _product(product_factory, name="Mouse X", slug="mouse-x")

        pc.categories.add(pcs)
        other_pc.categories.add(pcs)
        monitor.categories.add(monitors)
        mouse.categories.add(mice)

        picked, is_cross = suggested_products_for_product(pc)
        assert is_cross is True
        assert monitor in picked
        assert mouse in picked
        assert other_pc not in picked

    def test_accessory_product_keeps_same_category_related(self, product_factory):
        root = _ensure_branch(None, "Ноутбуки, планшети", "ноутбуки-планшети")
        accessories = _ensure_branch(root, "Аксесуари для ноутбуків", "аксесуари-для-ноутбуків")
        stands = _ensure_branch(accessories, "Підставки", "підставки-для-ноутбуків")

        stand_a = _product(product_factory, name="Stand A", slug="stand-a")
        stand_b = _product(product_factory, name="Stand B", slug="stand-b")
        stand_a.categories.add(stands)
        stand_b.categories.add(stands)

        picked, is_cross = suggested_products_for_product(stand_a)
        assert is_cross is False
        assert stand_b in picked

    def test_category_laptop_root_shows_accessories(self, product_factory):
        root = _ensure_branch(None, "Ноутбуки, планшети", "ноутбуки-планшети")
        laptops = _ensure_branch(root, "Ноутбуки", "ноутбуки")
        bags_root = _ensure_branch(root, "Сумки, рюкзаки, чохли", "сумки-рюкзаки-чохли")
        bags = _ensure_branch(bags_root, "Сумки до ноутбуків", "сумки-до-ноутбуків")

        bag = _product(product_factory, name="Bag 15", slug="bag-15")
        laptop = _product(product_factory, name="Laptop Z", slug="laptop-z")
        bag.categories.add(bags)
        laptop.categories.add(laptops)

        picked, is_cross = suggested_products_for_category(root)
        assert is_cross is True
        assert bag in picked
        assert laptop not in picked

    def test_laptop_department_listing_excludes_components(self, product_factory):
        from apps.catalog.services import category_listing_products

        root = _ensure_branch(None, "Ноутбуки, планшети", "ноутбуки-планшети")
        laptops = _ensure_branch(root, "Ноутбуки", "ноутбуки")
        components = _ensure_branch(root, "Комплектуючі до ноутбуків", "комплектуючі-до-ноутбуків")
        ssd = _ensure_branch(components, "Внутрішні SSD", "внутрішні-ssd")
        games = _ensure_branch(root, "Ігрові приставки", "ігрові-приставки")

        laptop = _product(product_factory, name="Laptop Z", slug="laptop-z-list")
        drive = _product(product_factory, name="SSD 512", slug="ssd-512")
        game = _product(product_factory, name="PS5 Game", slug="ps5-game")

        laptop.categories.add(laptops)
        drive.categories.add(ssd)
        game.categories.add(games)

        listed = set(category_listing_products(root).values_list("slug", flat=True))
        assert "laptop-z-list" in listed
        assert "ssd-512" not in listed
        assert "ps5-game" not in listed
        assert primary_listing_category_pks(root) is not None
