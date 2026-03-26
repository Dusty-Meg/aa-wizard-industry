"""App URLs"""

# Django
from django.urls import path

# AA wizardindustry App
from wizardindustry import views

app_name: str = "wizardindustry"

urlpatterns = [
    path("", views.index, name="index"),
    path("token/", views.add_or_refresh_token, name="token_add"),
    path("corporation/", views.corporation_blueprints, name="corporation_blueprints"),
    path("corporation/token/", views.add_or_refresh_corporation_token, name="corporation_token_add"),
]
