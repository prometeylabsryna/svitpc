from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail_view, name="detail"),
    path("add/<int:product_id>/", views.cart_add_view, name="add"),
    path("remove/<int:product_id>/", views.cart_remove_view, name="remove"),
    path("update/<int:product_id>/", views.cart_update_view, name="update"),
]
