from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def service_worker(request):
    """Serve SW at site root so scope '/' is allowed (not limited to /static/)."""
    sw_path = Path(settings.BASE_DIR) / "static" / "service-worker.js"
    response = HttpResponse(sw_path.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response
