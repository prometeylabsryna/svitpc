from django.urls import path

from . import views

app_name = "wishlist"

urlpatterns = [
    path("", views.wishlist_page_view, name="page"),
    path("toggle/<int:product_id>/", views.toggle_view, name="toggle"),
]
