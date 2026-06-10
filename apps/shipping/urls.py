from django.urls import path

from . import views

app_name = "shipping"

urlpatterns = [
    path("np/cities/", views.np_cities_view, name="np_cities"),
    path("np/warehouses/", views.np_warehouses_view, name="np_warehouses"),
    path("up/postoffice/", views.up_postoffice_view, name="up_postoffice"),
    path("delivery-cost/", views.delivery_cost_view, name="delivery_cost"),
]
