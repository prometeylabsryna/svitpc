from django.http import HttpRequest

from apps.core.admin_mixins import is_admin_request

from .views import COMPARE_KEY


def compare_context(request: HttpRequest) -> dict:
    if is_admin_request(request):
        return {}
    ids = list(request.session.get(COMPARE_KEY, []))
    return {"compare_count": len(ids), "compare_ids": ids}
