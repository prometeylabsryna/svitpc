from django.urls import path

from . import views

app_name = "pages"

urlpatterns = [
    path("delivery/", views.delivery_view, name="delivery"),
    path("payment/", views.payment_view, name="payment"),
    path("warranty/", views.warranty_view, name="warranty"),
    path("returns/", views.returns_view, name="returns"),
    path("contact/", views.contact_view, name="contact"),
    path("privacy/", views.privacy_view, name="privacy"),
    path("<uslug:slug>/", views.page_detail_view, name="detail"),
]
