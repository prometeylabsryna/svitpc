from django.urls import path

from . import views

urlpatterns = [
    path("google-merchant.xml", views.google_merchant_feed_view, name="google_merchant"),
]
