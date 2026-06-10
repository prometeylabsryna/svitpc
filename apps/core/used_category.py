"""Site-wide visibility for the optional used-goods (Б/У) catalog branch."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.catalog.models import Category


def hidden_used_category_pks() -> frozenset[int]:
    """Category PKs hidden from nav and public URLs (root + descendants)."""
    from apps.core.models import SiteSettings

    site = SiteSettings.load()
    if site.show_used_category or not site.used_category_id:
        return frozenset()

    from apps.catalog.models import Category

    try:
        root = Category.objects.get(pk=site.used_category_id, is_active=True)
    except Category.DoesNotExist:
        return frozenset()

    return frozenset(root.get_descendants(include_self=True).values_list("pk", flat=True))


def is_used_category_branch(category: Category) -> bool:
    return category.pk in hidden_used_category_pks()
