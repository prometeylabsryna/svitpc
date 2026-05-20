from django.urls import path
from apps.payments.views import liqpay_webhook_view, monobank_webhook_view, wayforpay_webhook_view

urlpatterns = [
    path("liqpay/", liqpay_webhook_view, name="webhook_liqpay"),
    path("wayforpay/", wayforpay_webhook_view, name="webhook_wayforpay"),
    path("monobank/", monobank_webhook_view, name="webhook_monobank"),
]
