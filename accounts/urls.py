from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("register/", views.register, name="register"),
    path("validate/", views.validate_registration, name="validate"),
    path("login/", views.StoreLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
]
