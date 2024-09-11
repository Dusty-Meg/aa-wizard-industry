"""App Configuration"""

# Django
from django.apps import AppConfig

# AA wizardindustry App
from wizardindustry import __version__


class wizardindustryConfig(AppConfig):
    """App Config"""

    name = "wizardindustry"
    label = "wizardindustry"
    verbose_name = f"wizardindustry App v{__version__}"
