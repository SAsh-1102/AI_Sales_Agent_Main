# call/urls.py
from django.urls import path
from . import views # type: ignore

urlpatterns = [
    path("", views.room, name="room"),  # room.html page
]
