import pytest

from apps.catalog.category_icons import resolve_category_icon_id
from apps.catalog.models import Category


@pytest.mark.django_db
class TestCategoryIcons:
    def test_gsm_modem_slug(self):
        cat = Category(name="GSM модеми", slug="gsm-modemy")
        assert resolve_category_icon_id(cat) == "modem"

    def test_xdsl_slug(self):
        cat = Category(name="xDSL обладнання", slug="xdsl-obladnannya")
        assert resolve_category_icon_id(cat) == "modem"

    def test_interactive_board(self):
        cat = Category(name="Інтерактивні дошки", slug="interaktyvni-doshky")
        assert resolve_category_icon_id(cat) == "board"

    def test_used_category(self):
        cat = Category(name="Б/У", slug="bu")
        assert resolve_category_icon_id(cat) == "used"

    def test_large_appliance(self):
        cat = Category(name="Велика побутова техніка", slug="velyka-pobutova-tehnika")
        assert resolve_category_icon_id(cat) == "appliance-large"

    def test_gadgets(self):
        cat = Category(name="Гаджети (Hi-Tech)", slug="hadzhety-hi-tech")
        assert resolve_category_icon_id(cat) == "smart-home"

    def test_small_appliance(self):
        cat = Category(name="Дрібна побутова техніка", slug="dribna-pobutova-tehnika")
        assert resolve_category_icon_id(cat) == "appliance-small"

    def test_gadgets_and_small_appliance_resolve_differently(self):
        gadgets = Category(name="Гаджети (Hi-Tech)", slug="hadzhety-hi-tech")
        small = Category(name="Дрібна побутова техніка", slug="dribna-pobutova-tehnika")
        assert resolve_category_icon_id(gadgets) != resolve_category_icon_id(small)

    def test_laptop_by_name(self):
        cat = Category(name="Ноутбуки", slug="notebooks")
        assert resolve_category_icon_id(cat) == "laptop"

    def test_default_fallback(self):
        cat = Category(name="Інше", slug="inshe")
        assert resolve_category_icon_id(cat) == "default"
