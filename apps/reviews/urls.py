from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("product/<int:product_id>/", views.product_reviews_view, name="product"),
    path("product/<int:product_id>/submit/", views.submit_review_view, name="submit"),
]
