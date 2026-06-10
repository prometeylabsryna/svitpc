"""Tests for session-based Cart class."""

from decimal import Decimal
from unittest.mock import MagicMock


def make_session(**items):
    """Return a MagicMock dict-like session with pre-loaded cart items."""
    from apps.cart.cart import CART_SESSION_KEY

    data = {CART_SESSION_KEY: items}
    session = MagicMock()
    session.__getitem__ = lambda self, key: data[key]
    session.__setitem__ = lambda self, key, val: data.__setitem__(key, val)
    session.get = lambda key, default=None: data.get(key, default)
    return session


def make_request(**cart_items):
    request = MagicMock()
    request.session = make_session(**cart_items)
    return request


class TestCart:
    def test_empty_cart(self):
        from apps.cart.cart import Cart

        cart = Cart(make_request())
        assert cart.item_count == 0
        assert cart.total == Decimal("0")
        assert isinstance(cart.total, Decimal)

    def test_remove_item(self):
        from apps.cart.cart import Cart, CART_SESSION_KEY

        session_data = {
            "5": {"qty": 1, "price": "50.00", "name": "X", "slug": "x", "image_url": ""}
        }
        request = MagicMock()
        request.session.get = lambda key, default=None: session_data if key == CART_SESSION_KEY else default
        request.session.__setitem__ = MagicMock()

        cart = Cart(request)
        assert cart.item_count == 1
        cart.remove(5)
        assert cart.item_count == 0

    def test_total_calculation(self):
        from apps.cart.cart import Cart, CART_SESSION_KEY

        session_data = {
            "1": {"qty": 2, "price": "100.00", "name": "A", "slug": "a", "image_url": ""},
            "2": {"qty": 1, "price": "200.00", "name": "B", "slug": "b", "image_url": ""},
        }
        request = MagicMock()
        request.session.get = lambda key, default=None: session_data if key == CART_SESSION_KEY else default
        request.session.__setitem__ = MagicMock()

        cart = Cart(request)
        assert cart.total == Decimal("400.00")

    def test_peek_returns_snapshot(self):
        from apps.cart.cart import Cart, CART_SESSION_KEY

        session_data = {
            "3": {"qty": 2, "price": "75.00", "name": "Y", "slug": "y", "image_url": ""}
        }
        request = MagicMock()
        request.session.get = lambda key, default=None: session_data if key == CART_SESSION_KEY else default
        request.session.__setitem__ = MagicMock()

        cart = Cart(request)
        item = cart.peek(3)
        assert item is not None
        assert item["product_id"] == 3
        assert item["qty"] == 2
        assert item["price"] == Decimal("75.00")

    def test_peek_missing_returns_none(self):
        from apps.cart.cart import Cart

        cart = Cart(make_request())
        assert cart.peek(999) is None

    def test_iter_yields_items_with_subtotal(self):
        from apps.cart.cart import Cart, CART_SESSION_KEY

        session_data = {
            "1": {"qty": 3, "price": "10.00", "name": "X", "slug": "x", "image_url": ""},
        }
        request = MagicMock()
        request.session.get = lambda key, default=None: session_data if key == CART_SESSION_KEY else default
        request.session.__setitem__ = MagicMock()

        cart = Cart(request)
        items = list(cart)
        assert len(items) == 1
        assert items[0]["subtotal"] == Decimal("30.00")
