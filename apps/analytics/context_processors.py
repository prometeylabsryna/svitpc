from django.conf import settings
from django.http import HttpRequest


def analytics_context(request: HttpRequest) -> dict:
    return {
        "GOOGLE_ANALYTICS_ID": settings.GOOGLE_ANALYTICS_ID,
        "GOOGLE_TAG_MANAGER_ID": settings.GOOGLE_TAG_MANAGER_ID,
        "GOOGLE_ADS_ID": settings.GOOGLE_ADS_ID,
    }
