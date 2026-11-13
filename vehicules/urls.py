from django.urls import path

from . import views

app_name = "vehicules"

urlpatterns = [
    path("", views.index, name="index"),
]
