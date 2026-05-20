from django.urls import path

from . import views

app_name = "promotions"

urlpatterns = [
    path("", views.promotions_list_view, name="list"),
]
