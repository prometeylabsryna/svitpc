from django.urls import path

from . import views

app_name = "checkout"

urlpatterns = [
    path("", views.checkout_step1_view, name="step1"),
    path("payment/", views.checkout_step2_view, name="step2"),
    path("confirm/", views.checkout_confirm_view, name="confirm"),
    path("success/<int:pk>/", views.checkout_success_view, name="success"),
    path("one-click/<int:product_id>/", views.one_click_view, name="one_click"),
]
