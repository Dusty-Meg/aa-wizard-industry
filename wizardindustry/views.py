"""App Views"""

# Third Party
from blueprints.models import Blueprint

# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.html import format_html
from django.utils.translation import gettext_lazy

# Alliance Auth
from allianceauth.authentication.models import CharacterOwnership, User
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from esi.decorators import token_required

# Alliance Auth (External Libs)
from eveuniverse.models import EveMarketGroup

from .models import Owner, CorporationAdmin
from .utils import messages_plus
from .view_models import (
    owned_blueprints,
    owned_blueprints_blueprints,
    owned_blueprints_market_groups,
)


@login_required
@permission_required("wizardindustry.add_corporation")
@token_required(
    scopes=[
        "esi-corporations.read_blueprints.v1",
        "esi-assets.read_corporation_assets.v1",
        "esi-contracts.read_corporation_contracts.v1",
        "esi-industry.read_corporation_jobs.v1",
        "esi-markets.read_corporation_orders.v1",
        "esi-characters.read_corporation_roles.v1",
        "esi-universe.read_structures.v1",
    ]
)
def setup_corporation(request, token):
    success = True
    token_char = EveCharacter.objects.get(character_id=token.character_id)

    try:
        owned_char = CharacterOwnership.objects.get(
            user=request.user, character=token_char
        )
    except CharacterOwnership.DoesNotExist:
        messages_plus.error(
            request,
            format_html(
                gettext_lazy(
                    "You can only use your main or alt characters "
                    "to add corporations. "
                    "However, character %s is neither. "
                )
                % format_html("<strong>{}</strong>", token_char.character_name)
            ),
        )
        success = False

    if success:
        try:
            corporation = EveCorporationInfo.objects.get(
                corporation_id=token_char.corporation_id
            )
        except EveCorporationInfo.DoesNotExist:
            corporation = EveCorporationInfo.objects.create_corporation(
                token_char.corporation_id,
            )

        with transaction.atomic():
            owner, _ = Owner.objects.update_or_create(
                corporation=corporation,
                character=owned_char,
                user=request.user,
                corporation_owner=True,
            )

            owner.save()

        corporation_admin = CorporationAdmin.objects.get_or_create(
            corporation=corporation
        )

        corporation_admin[0].admin_users.add(request.user)
        corporation_admin[0].save()

    return redirect("wizardindustry:index")


@login_required
@permission_required("wizardindustry.manage_corporations")
def corporation_admin(request):
    database_corporations = request.user.wizardIndustryCorporationAdmins.all()

    if not database_corporations:
        return redirect("wizardindustry:index")
    
    corporations = []

    for corp in database_corporations:
        corporations.append({"name": corp.corporation.corporation_name, "id": corp.corporation.corporation_id})
    model = {"corporation_list": corporations}

    if len(corporations) == 1:
        model["corporation"] = database_corporations[0]

    if request.method == "POST":
        corporation_id = request.POST.get("corporation_id")
        if corporation_id:
            try:
                selected_corp_id = int(corporation_id)
                for corp in database_corporations:
                    if corp.corporation.corporation_id == selected_corp_id:
                        model["corporation"] = corp
                        break
            except (ValueError, TypeError):
                pass

            if request.POST.get("action") == "save_users":
                post_data_admin_users = request.POST.getlist("to")
                post_data_users = request.POST.getlist("to_2")

                for manager_user in model["corporation"].admin_users.all():
                    if str(manager_user.username) not in post_data_admin_users:
                        model["corporation"].admin_users.remove(manager_user)

                for user in model["corporation"].users.all():
                    if str(user.username) not in post_data_users:
                        model["corporation"].users.remove(user)

                for admin_username in post_data_admin_users:
                    try:
                        manager_user = User.objects.get(username=admin_username)
                        if manager_user not in model["corporation"].admin_users.all():
                            model["corporation"].admin_users.add(manager_user)
                    except User.DoesNotExist:
                        continue

                for username in post_data_users:
                    try:
                        user = User.objects.get(username=username)
                        if user not in model["corporation"].users.all():
                            model["corporation"].users.add(user)
                    except User.DoesNotExist:
                        continue

                model["corporation"].save()

    if model.get("corporation") is not None:
        corporation = model.get("corporation")
        excluded_user_ids = set()
        excluded_user_ids.update(corporation.admin_users.values_list('id', flat=True))
        excluded_user_ids.update(corporation.users.values_list('id', flat=True))
        users = User.objects.exclude(id__in=excluded_user_ids).filter(character_ownerships__isnull=False).filter(is_active=True).all()
        model["available_users"] = users
        model["manager_users"] = corporation.admin_users.all()
        model["users"] = corporation.users.all()

    return render(request, "wizardindustry/corporation_admin.html", model)


@login_required
@permission_required("wizardindustry.add_character")
@token_required(
    scopes=[
        "esi-characters.read_blueprints.v1",
        "esi-assets.read_assets.v1",
        "esi-contracts.read_character_contracts.v1",
        "esi-industry.read_character_jobs.v1",
        "esi-markets.read_character_orders.v1",
    ]
)
def setup_character(request, token):
    success = True
    token_char = EveCharacter.objects.get(character_id=token.character_id)

    try:
        owned_char = CharacterOwnership.objects.get(
            user=request.user, character=token_char
        )
    except CharacterOwnership.DoesNotExist:
        messages_plus.error(
            request,
            format_html(
                gettext_lazy(
                    "You can only use your main or alt characters "
                    "to add corporations. "
                    "However, character %s is neither. "
                )
                % format_html("<strong>{}</strong>", token_char.character_name)
            ),
        )
        success = False

    if success:
        try:
            corporation = EveCorporationInfo.objects.get(
                corporation_id=token_char.corporation_id
            )
        except EveCorporationInfo.DoesNotExist:
            corporation = EveCorporationInfo.objects.create_corporation(
                token_char.corporation_id,
            )

        with transaction.atomic():
            owner, _ = Owner.objects.update_or_create(
                corporation=corporation,
                character=owned_char,
                user=request.user,
                corporation_owner=False,
            )

            owner.save()

    return redirect("wizardindustry:index")


@login_required
@permission_required("wizardindustry.basic_access")
def index(request: WSGIRequest) -> HttpResponse:
    models = {}

    owners = Owner.objects.all()

    # for owner in owners:
    #     owner._get_assets()

    return render(request, "wizardindustry/index.html", models)


@login_required
@permission_required("wizardindustry.blueprint_pokemon")
def blueprint_pokemon(request: WSGIRequest) -> HttpResponse:
    """
    Index view
    :param request:
    :return:
    """

    owned_blueprint_list = (
        Blueprint.objects.user_has_access(request.user).filter(runs=None).all()
    )
    blueprint_marketgroups = EveMarketGroup.objects.filter(parent_market_group__id=2)

    view_model = owned_blueprints()

    view_model.market_groups = _market_cycler(
        blueprint_marketgroups, owned_blueprint_list
    )

    context = {"model": view_model}

    return render(request, "wizardindustry/allblueprints.html", context)


def _market_cycler(blueprint_marketgroups, owned_blueprints):
    models = []

    bad_bpos = [
        47969,
        48469,
        48470,
        47971,
        48471,
        48472,
        47973,
        48473,
        48474,
        48095,
        58973,
        58974,
        49973,
        60514,
    ]

    for market_group in blueprint_marketgroups:
        market_group_view_model = owned_blueprints_market_groups()
        market_group_view_model.market_group_id = market_group.id
        market_group_view_model.market_group_name = market_group.name
        market_group_view_model.description = market_group.description
        market_group_view_model.blueprints = []

        for eve_type in market_group.eve_types.filter(published=True).all():
            if eve_type.name.startswith("Civilian"):
                continue

            if eve_type.id in bad_bpos:
                continue

            if eve_type is not None:
                activity_product_product = eve_type.industry_products.filter(
                    activity_id=1
                ).first()
                if not hasattr(activity_product_product, "product_eve_type"):
                    continue
                activity_product_product = activity_product_product.product_eve_type

                if (
                    hasattr(activity_product_product, "inv_meta_types")
                    and activity_product_product.inv_meta_types is not None
                    and activity_product_product.inv_meta_types.meta_group_id != 1
                    and activity_product_product.inv_meta_types.meta_group_id != 54
                ):
                    continue

            blueprint_view_model = owned_blueprints_blueprints()
            blueprint_view_model.blueprint_id = eve_type.id
            blueprint_view_model.blueprint_name = eve_type.name
            blueprint_view_model.base_cost = (
                eve_type.base_price.base_price
                if hasattr(eve_type, "base_price") and eve_type.base_price is not None
                else 0
            )

            blueprint = owned_blueprints.filter(eve_type=eve_type).first()
            if blueprint:
                blueprint_view_model.owned_count = 1
            else:
                blueprint_view_model.owned_count = 0

            market_group_view_model.blueprints.append(blueprint_view_model)

        market_group_view_model.blueprint_count = len(
            market_group_view_model.blueprints
        )

        if len(market_group.market_group_children.all()) > 0:
            market_group_view_model.sub_groups = _market_cycler(
                market_group.market_group_children.all(), owned_blueprints
            )

        models.append(market_group_view_model)

    return models
