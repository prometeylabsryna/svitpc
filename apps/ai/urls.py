from django.urls import path

from . import views

app_name = "ai"

urlpatterns = [
    path("consultant/", views.consultant_view, name="consultant"),
    path("consultant/stream/", views.consultant_stream_view, name="consultant_stream"),
    path("compatibility/", views.compatibility_check_view, name="compatibility_check"),
]
