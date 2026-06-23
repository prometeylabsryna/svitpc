"""Site-wide visibility for the optional used-goods (Б/У) catalog branch."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.catalog.models import Category


HIDDEN_USED_CATEGORY_PKS_KEY = "core.hidden_used_category_pks"


def hidden_used_category_pks() -> frozenset[int]:
    """Category PKs hidden from nav and public URLs (root + descendants)."""
    from django.core.cache import cache

    cached = cache.get(HIDDEN_USED_CATEGORY_PKS_KEY)
    if cached is not None:
        return cached

    from apps.core.models import SiteSettings

    site = SiteSettings.load()
    if site.show_used_category or not site.used_category_id:
        result = frozenset()
    else:
        from apps.catalog.models import Category

        try:
            root = Category.objects.get(pk=site.used_category_id, is_active=True)
        except Category.DoesNotExist:
            result = frozenset()
        else:
            result = frozenset(root.get_descendants(include_self=True).values_list("pk", flat=True))

    cache.set(HIDDEN_USED_CATEGORY_PKS_KEY, result, timeout=None)
    return result


def invalidate_hidden_used_category_cache() -> None:
    from django.core.cache import cache

    cache.delete(HIDDEN_USED_CATEGORY_PKS_KEY)


def is_used_category_branch(category: Category) -> bool:
    return category.pk in hidden_used_category_pks()
