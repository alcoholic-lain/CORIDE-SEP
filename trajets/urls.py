from django.urls import path

from . import views

app_name = "trajets"

urlpatterns = [
    path("", views.index, name="index"),
]
