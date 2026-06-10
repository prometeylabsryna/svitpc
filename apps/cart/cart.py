"""Session-based cart implementation."""

from __future__ import annotations

from decimal import Decimal

from django.http import HttpRequest

CART_SESSION_KEY = "svitpc_cart"


class Cart:
    def __init__(self, request: HttpRequest) -> None:
        self.session = request.session
        self._cart: dict[str, dict] = self.session.get(CART_SESSION_KEY, {})

    def _save(self) -> None:
        self.session[CART_SESSION_KEY] = self._cart
        self.session.modified = True

    def add(self, product_id: int, qty: int = 1, override: bool = False) -> None:
        key = str(product_id)
        if key not in self._cart:
            from apps.catalog.models import Product

            try:
                p = Product.objects.only("price", "name", "slug", "image_url").get(pk=product_id, is_visible=True)
            except Product.DoesNotExist:
                return
            self._cart[key] = {
                "qty": 0,
                "price": str(p.price),
                "name": p.name,
                "slug": p.slug,
                "image_url": p.main_image_url,
            }
        if override:
            self._cart[key]["qty"] = qty
        else:
            self._cart[key]["qty"] += qty
        self._save()

    def peek(self, product_id: int) -> dict | None:
        """Return cart line snapshot without mutating the cart."""
        item = self._cart.get(str(product_id))
        if not item:
            return None
        return {
            "product_id": product_id,
            "qty": item["qty"],
            "price": Decimal(item["price"]),
            "name": item["name"],
            "slug": item["slug"],
            "image_url": item["image_url"],
        }

    def remove(self, product_id: int) -> None:
        key = str(product_id)
        self._cart.pop(key, None)
        self._save()

    def update_qty(self, product_id: int, qty: int) -> None:
        key = str(product_id)
        if key in self._cart:
            if qty <= 0:
                self.remove(product_id)
            else:
                self._cart[key]["qty"] = qty
                self._save()

    def clear(self) -> None:
        self._cart.clear()
        self._save()

    def __iter__(self):
        for key, item in self._cart.items():
            yield {
                "product_id": int(key),
                "qty": item["qty"],
                "price": Decimal(item["price"]),
                "name": item["name"],
                "slug": item["slug"],
                "image_url": item["image_url"],
                "subtotal": Decimal(item["price"]) * item["qty"],
            }

    def __len__(self) -> int:
        return sum(item["qty"] for item in self._cart.values())

    @property
    def total(self) -> Decimal:
        return sum(
            (Decimal(i["price"]) * i["qty"] for i in self._cart.values()),
            Decimal("0"),
        )

    @property
    def item_count(self) -> int:
        return len(self._cart)
