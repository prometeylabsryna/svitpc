from django.urls import path

from . import views

app_name = "bots"

urlpatterns = [
    path("webhook/", views.telegram_webhook_view, name="telegram_webhook"),
]
