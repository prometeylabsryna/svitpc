from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST


def consultant_view(request: HttpRequest) -> HttpResponse:
    product_name = request.GET.get("product", "").strip()[:200]
    return render(request, "ai/consultant.html", {"prefill_product": product_name})


@require_POST
def consultant_stream_view(request: HttpRequest) -> StreamingHttpResponse:
    from .services.consultant import stream_consultant

    message = request.POST.get("message", "").strip()
    if not message:
        return HttpResponse(status=400)

    return StreamingHttpResponse(
        stream_consultant(message),
        content_type="text/event-stream",
    )


@require_POST
def compatibility_check_view(request: HttpRequest) -> JsonResponse:
    """Check hardware compatibility for a list of product IDs. Returns JSON."""
    import json
    from .services.consultant import check_compatibility

    try:
        raw = request.POST.get("product_ids", "[]")
        product_ids = [int(i) for i in json.loads(raw)]
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "Невірний формат product_ids"}, status=400)

    if len(product_ids) < 2:
        return JsonResponse({"error": "Потрібно як мінімум 2 товари"}, status=400)

    result = check_compatibility(product_ids)
    return JsonResponse({"result": result})
