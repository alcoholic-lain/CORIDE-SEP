from django.urls import path

from . import views

app_name = "coride"

urlpatterns = [
    path("", views.index, name="index"),
]
