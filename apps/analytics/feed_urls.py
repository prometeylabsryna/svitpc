from django.urls import path

from . import views

urlpatterns = [
    path("google-merchant.xml", views.google_merchant_feed_view, name="google_merchant"),
    path("google-ads-remarketing.xml", views.google_ads_remarketing_feed_view, name="google_ads"),
    path("google-merchant-cheap.xml", views.google_merchant_cheap_feed_view, name="google_merchant_cheap"),
    path("google-merchant-medium.xml", views.google_merchant_medium_feed_view, name="google_merchant_medium"),
    path("google-merchant-expensive.xml", views.google_merchant_expensive_feed_view, name="google_merchant_expensive"),
]
