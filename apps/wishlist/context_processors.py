from django.http import HttpRequest

from .cache import get_cached_wishlist_ids, invalidate_wishlist_ids_cache, set_cached_wishlist_ids

_SESSION_KEY = "wishlist"


def wishlist_context(request: HttpRequest) -> dict:
    if request.user.is_authenticated:
        user_id = request.user.pk
        ids = get_cached_wishlist_ids(user_id)
        if ids is None:
            ids = list(request.user.wishlist.values_list("product_id", flat=True))
            set_cached_wishlist_ids(user_id, ids)
    else:
        ids = list(request.session.get(_SESSION_KEY, []))
    return {"wishlist_ids": ids, "wishlist_count": len(ids)}
