from django.urls import path

from . import views

app_name = "utilisateurs"

urlpatterns = [
    path("", views.index, name="index"),
]
