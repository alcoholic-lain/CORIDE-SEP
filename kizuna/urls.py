from django.urls import path

from . import views

app_name = "kizuna"

urlpatterns = [
    path("", views.index, name="index"),
]
