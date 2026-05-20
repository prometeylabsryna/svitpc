from rest_framework.routers import DefaultRouter
from django.urls import path, include

from . import views

router = DefaultRouter()
router.register("products", views.ProductViewSet, basename="products")
router.register("categories", views.CategoryViewSet, basename="categories")
router.register("brands", views.BrandViewSet, basename="brands")

app_name = "api"

urlpatterns = [
    path("", include(router.urls)),
    path("cart/", views.cart_info),
]
