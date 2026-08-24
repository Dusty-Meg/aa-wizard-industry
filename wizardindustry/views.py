"""App Views"""

# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from esi.decorators import token_required

from .view_models import (
    owned_blueprints,
    owned_blueprints_market_groups,
    owned_blueprints_blueprints
)

from eve_sde.models import ItemMarketGroup, BlueprintActivity
from .models import CharacterBlueprint, CorporationBlueprint, CorporationBlueprintSync
from .app_settings import WIZARDINDUSTRY_BLUEPRINT_SCOPE, WIZARDINDUSTRY_CORPORATION_BLUEPRINT_SCOPE


@login_required
@permission_required("wizardindustry.basic_access")
def index(request: WSGIRequest) -> HttpResponse:
    """
    Index view
    :param request:
    :return:
    """

    owned_blueprint_type_ids = set(
        CharacterBlueprint.objects.filter(
            user=request.user,
            is_original=True,
        ).values_list("eve_type_id", flat=True)
    )
    blueprint_marketgroups = ItemMarketGroup.objects.filter(parent_group__id=2)

    view_model = owned_blueprints()

    view_model.market_groups = _market_cycler(blueprint_marketgroups, owned_blueprint_type_ids)

    context = {"model": view_model}

    return render(request, "wizardindustry/allblueprints.html", context)


@login_required
@permission_required("wizardindustry.basic_access")
@token_required(scopes=[WIZARDINDUSTRY_BLUEPRINT_SCOPE], new=False)
def add_or_refresh_token(request: WSGIRequest, token) -> HttpResponse:
    return redirect("wizardindustry:index")


@login_required
@permission_required("wizardindustry.basic_access")
@token_required(scopes=[WIZARDINDUSTRY_CORPORATION_BLUEPRINT_SCOPE], new=False)
def add_or_refresh_corporation_token(request: WSGIRequest, token) -> HttpResponse:
    return redirect("wizardindustry:corporation_blueprints")


@login_required
@permission_required("wizardindustry.basic_access")
def corporation_blueprints(request: WSGIRequest) -> HttpResponse:
    allowed_corporations = list(
        CorporationBlueprintSync.objects.filter(
            user=request.user,
        ).order_by("corporation_name", "corporation_id").values("corporation_id", "corporation_name")
    )

    selected_corporation_id = request.GET.get("corporation_id")
    if selected_corporation_id is None and allowed_corporations:
        selected_corporation_id = str(allowed_corporations[0]["corporation_id"])

    view_model = None
    if selected_corporation_id is not None:
        owned_blueprint_type_ids = set(
            CorporationBlueprint.objects.filter(
                user=request.user,
                corporation_id=selected_corporation_id,
                is_original=True,
            ).values_list("eve_type_id", flat=True)
        )
        blueprint_marketgroups = ItemMarketGroup.objects.filter(parent_group__id=2)

        view_model = owned_blueprints()

        view_model.market_groups = _market_cycler(blueprint_marketgroups, owned_blueprint_type_ids)

    context = {
        "corporations": allowed_corporations,
        "selected_corporation_id": selected_corporation_id,
        "corporation_blueprints": view_model,
    }

    return render(request, "wizardindustry/corporation_blueprints.html", context)


def _market_cycler(blueprint_marketgroups, owned_blueprint_type_ids):
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
        92182,
        86180,
        86179,
        86178,
        85232
    ]

    for market_group in blueprint_marketgroups:
        market_group_view_model = owned_blueprints_market_groups()
        market_group_view_model.market_group_id = market_group.id
        market_group_view_model.market_group_name = market_group.name
        market_group_view_model.description = market_group.description
        market_group_view_model.blueprints = []

        for eve_type in market_group.itemtype_set.filter(published=True).all():
            if eve_type.name.startswith('Civilian'):
                continue

            if eve_type.id in bad_bpos:
                continue

            if eve_type is not None:
                blueprint_activity = BlueprintActivity.objects.filter(
                    blueprint_item_type=eve_type,
                    activity=BlueprintActivity.Activities.manufacturing,
                ).first()
                if blueprint_activity is None:
                    continue

                activity_product_product = blueprint_activity.products.first()
                if activity_product_product is None or activity_product_product.item_type is None:
                    continue
                activity_product_product = activity_product_product.item_type

                if hasattr(activity_product_product, 'meta_group_id_raw') and activity_product_product.meta_group_id_raw is not None and activity_product_product.meta_group_id_raw != 1 and activity_product_product.meta_group_id_raw != 54:
                    continue

            blueprint_view_model = owned_blueprints_blueprints()
            blueprint_view_model.blueprint_id = eve_type.id
            blueprint_view_model.blueprint_name = eve_type.name
            blueprint_view_model.base_cost = eve_type.base_price if hasattr(eve_type, 'base_price') and eve_type.base_price is not None else 0

            if eve_type.id in owned_blueprint_type_ids:
                blueprint_view_model.owned_count = 1
            else:
                blueprint_view_model.owned_count = 0

            market_group_view_model.blueprints.append(blueprint_view_model)

        market_group_view_model.blueprint_count = len(market_group_view_model.blueprints)

        if len(market_group.children.all()) > 0:
            market_group_view_model.sub_groups = _market_cycler(market_group.children.all(), owned_blueprint_type_ids)

        models.append(market_group_view_model)

    return models
