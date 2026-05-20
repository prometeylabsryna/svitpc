from django.urls import path

from .views import subscribe_push_view, unsubscribe_push_view

app_name = "notifications"
urlpatterns = [
    path("subscribe/", subscribe_push_view, name="subscribe"),
    path("unsubscribe/", unsubscribe_push_view, name="unsubscribe"),
]
