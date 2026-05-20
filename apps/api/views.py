"""DRF API v1 stubs for mobile app."""

from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.catalog.models import Brand, Category, Product
from apps.orders.models import Order


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "slug", "sku", "price", "old_price", "stock", "is_visible", "main_image_url", "avg_rating", "review_count")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent_id", "is_active")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "name", "slug")


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_visible=True).select_related("brand")
    serializer_class = ProductSerializer
    filterset_fields = ("brand", "is_new", "is_hit")
    search_fields = ("name", "sku")
    ordering_fields = ("price", "date_added", "name")


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


@api_view(["GET"])
def cart_info(request) -> Response:
    from apps.cart.cart import Cart
    cart = Cart(request)
    return Response({"count": len(cart), "total": str(cart.total), "items": list(cart)})
