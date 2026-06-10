from django.http import HttpRequest

_SESSION_KEY = "wishlist"


def wishlist_context(request: HttpRequest) -> dict:
    if request.user.is_authenticated:
        ids = list(request.user.wishlist.values_list("product_id", flat=True))
    else:
        ids = list(request.session.get(_SESSION_KEY, []))
    return {"wishlist_ids": ids, "wishlist_count": len(ids)}
