from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("register/modal/", views.register_modal_view, name="register_modal"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.dashboard_view, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("addresses/", views.addresses_view, name="addresses"),
    path("addresses/add/", views.address_create_view, name="address_create"),
    path("addresses/<int:pk>/delete/", views.address_delete_view, name="address_delete"),
]
