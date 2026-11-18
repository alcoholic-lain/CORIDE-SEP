from django.urls import path

from . import views

app_name = "m5"

urlpatterns = [
    path("", views.index, name="index"),
]
