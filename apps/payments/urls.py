from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("pay/<int:order_id>/", views.initiate_payment_view, name="initiate"),
]
