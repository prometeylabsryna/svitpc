"""Chat — HTMX-based widget views."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST


def chat_widget_view(request: HttpRequest) -> HttpResponse:
    return render(request, "chat/widget.html")


@require_POST
def chat_send_view(request: HttpRequest) -> HttpResponse:
    text = request.POST.get("text", "").strip()
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key or "anon"

    if text:
        from .models import ChatMessage, ChatSession

        session, _ = ChatSession.objects.get_or_create(session_key=session_key)
        ChatMessage.objects.create(session=session, role="customer", text=text)

        from django.conf import settings

        if settings.TELEGRAM_ADMIN_CHAT_ID:
            from apps.notifications.service import send_notification

            send_notification(
                "telegram",
                settings.TELEGRAM_ADMIN_CHAT_ID,
                "chat_message",
                {"text": text, "session_key": session_key},
            )

    return render(request, "chat/message_sent.html", {"text": text})
