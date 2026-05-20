from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("brands/", views.brands_list_view, name="brands"),
    path("brands/<uslug:slug>/", views.brand_view, name="brand"),
    path("new/", views.new_products_view, name="new_products"),
    path("hits/", views.hit_products_view, name="hit_products"),
    path("sale/", views.sale_products_view, name="sale_products"),
    path("category/<uslug:slug>/", views.category_view, name="category"),
    path("product/<uslug:slug>/", views.product_detail_view, name="product"),
]
