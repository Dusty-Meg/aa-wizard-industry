"""App URLs"""

# Django
from django.urls import path

# AA wizardindustry App
from wizardindustry import views

app_name: str = "wizardindustry"  # pylint: disable=invalid-name

urlpatterns = [
    path("", views.index, name="index"),
    path("setup_character", views.setup_character, name="setup_character"),
    path("setup_corporation", views.setup_corporation, name="setup_corporation"),
    path("blueprint_pokemon", views.blueprint_pokemon, name="blueprint_pokemon"),
]
