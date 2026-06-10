from django.urls import path

from . import views, warranty_views

app_name = "services"

urlpatterns = [
    path("", views.service_list_view, name="list"),
    path("prices/", views.service_prices_view, name="prices"),
    path("warranty/", warranty_views.warranty_list_view, name="warranty_list"),
    path("warranty/create/", warranty_views.warranty_create_view, name="warranty_create"),
    path("warranty/lookup-serial/", warranty_views.warranty_serial_lookup_view, name="warranty_serial_lookup"),
    path("warranty/product-search/", warranty_views.warranty_product_search_view, name="warranty_product_search"),
    path("warranty/product/<int:pk>/", warranty_views.warranty_product_pick_view, name="warranty_product_pick"),
    path("warranty/<int:pk>/submit/", warranty_views.warranty_claim_submit_view, name="warranty_submit"),
    path("<uslug:slug>/", views.service_detail_view, name="detail"),
]
