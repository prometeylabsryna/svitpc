from django.urls import path

from . import views

app_name = "compare"

urlpatterns = [
    path("", views.compare_page_view, name="page"),
    path("toggle/<int:product_id>/", views.toggle_view, name="toggle"),
    path("clear/", views.clear_view, name="clear"),
]
