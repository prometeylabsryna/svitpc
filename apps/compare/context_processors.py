from django.http import HttpRequest

from .views import COMPARE_KEY


def compare_context(request: HttpRequest) -> dict:
    ids = list(request.session.get(COMPARE_KEY, []))
    return {"compare_count": len(ids), "compare_ids": ids}
