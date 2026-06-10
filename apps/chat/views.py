"""Chat — disabled; redirects to contacts."""

from django.http import HttpRequest, HttpResponse, HttpResponseGone
from django.shortcuts import redirect
from django.views.decorators.http import require_POST


def chat_widget_view(request: HttpRequest) -> HttpResponse:
    return redirect("pages:contact")


@require_POST
def chat_send_view(request: HttpRequest) -> HttpResponse:
    return HttpResponseGone()
