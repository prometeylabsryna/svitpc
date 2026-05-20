from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.chat_widget_view, name="widget"),
    path("send/", views.chat_send_view, name="send"),
]
