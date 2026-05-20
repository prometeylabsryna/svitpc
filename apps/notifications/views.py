"""Push subscription views."""
from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from .models import PushSubscription


@require_POST
def subscribe_push_view(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"error": "auth required"}, status=401)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    endpoint = data.get("endpoint", "")
    keys = data.get("keys", {})
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        return JsonResponse({"error": "incomplete subscription"}, status=400)

    PushSubscription.objects.update_or_create(
        customer=request.user,
        endpoint=endpoint,
        defaults={"p256dh": keys["p256dh"], "auth": keys["auth"]},
    )
    return JsonResponse({"status": "subscribed"})


@require_POST
def unsubscribe_push_view(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({"error": "auth required"}, status=401)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid json"}, status=400)

    endpoint = data.get("endpoint", "")
    if endpoint:
        PushSubscription.objects.filter(customer=request.user, endpoint=endpoint).delete()
    return JsonResponse({"status": "unsubscribed"})
