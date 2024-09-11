"""Hook into Alliance Auth"""

# Django
from django.utils.translation import gettext_lazy as _

# Alliance Auth
from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

# AA wizardindustry App
from wizardindustry import urls


class wizardindustryMenuItem(MenuItemHook):
    """This class ensures only authorized users will see the menu entry"""

    def __init__(self):
        # setup menu entry for sidebar
        MenuItemHook.__init__(
            self,
            _("Wizard Industry"),
            "fas fa-cube fa-fw",
            "wizardindustry:index",
            navactive=["wizardindustry:"],
        )

    def render(self, request):
        """Render the menu item"""

        if request.user.has_perm("wizardindustry.basic_access"):
            return MenuItemHook.render(self, request)

        return ""


@hooks.register("menu_item_hook")
def register_menu():
    """Register the menu item"""

    return wizardindustryMenuItem()


@hooks.register("url_hook")
def register_urls():
    """Register app urls"""

    return UrlHook(urls, "wizardindustry", r"^wizardindustry/")
