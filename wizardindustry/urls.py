"""App URLs"""

# Django
from django.urls import path

# AA wizardindustry App
from wizardindustry import views

app_name: str = "wizardindustry"

urlpatterns = [
    path("/blueprint_pokemon", views.blueprint_pokemon, name="Blueprint Pokemon"),
]
