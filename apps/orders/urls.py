from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.order_list_view, name="list"),
    path("<int:pk>/", views.order_detail_view, name="detail"),
    path("<int:pk>/reorder/", views.reorder_view, name="reorder"),
]
