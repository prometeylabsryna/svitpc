from django.urls import path

from . import views

app_name = "search"

urlpatterns = [
    path("", views.results_view, name="results"),
    path("live/", views.live_search_view, name="live"),
]
