"""App Views"""

# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils.html import format_html
from django.utils.translation import gettext_lazy
from esi.decorators import token_required


from .view_models import (
    owned_blueprints,
    owned_blueprints_market_groups,
    owned_blueprints_blueprints
)

from .models import Owner

from buybackprogram.utils import messages_plus


from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from blueprints.models import Blueprint
from eveuniverse.models import EveMarketGroup, EveType, EveIndustryActivityProduct

@login_required
@permission_required("wizardindustry.add_corporation")
@token_required(
    scopes=[
        "esi-corporations.read_blueprints.v1",
        "esi-assets.read_corporation_assets.v1",
        "esi-contracts.read_corporation_contracts.v1",
        "esi-industry.read_corporation_jobs.v1",
        "esi-markets.read_corporation_orders.v1",
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
                corporation=corporation, character=owned_char, user=request.user
            )

            owner.save()

    return redirect("wizardindustry:index")


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
                corporation=corporation, character=owned_char, user=request.user
            )

            owner.save()

    return redirect("wizardindustry:index")

@login_required
@permission_required("wizardindustry.basic_access")
def index(request: WSGIRequest) -> HttpResponse:
    models = {}
    return render(request, "wizardindustry/index.html", models)


@login_required
@permission_required("wizardindustry.blueprint_pokemon")
def blueprint_pokemon(request: WSGIRequest) -> HttpResponse:
    """
    Index view
    :param request:
    :return:
    """

    owned_blueprint_list = Blueprint.objects.user_has_access(request.user).filter(runs=None).all()
    blueprint_marketgroups = EveMarketGroup.objects.filter(parent_market_group__id=2)

    view_model = owned_blueprints()

    view_model.market_groups = _market_cycler(blueprint_marketgroups, owned_blueprint_list)
        
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
        60514
    ]

    for market_group in blueprint_marketgroups:
        market_group_view_model = owned_blueprints_market_groups()
        market_group_view_model.market_group_id = market_group.id
        market_group_view_model.market_group_name = market_group.name
        market_group_view_model.description = market_group.description
        market_group_view_model.blueprints = []

        for eve_type in market_group.eve_types.filter(published=True).all():
            if eve_type.name.startswith('Civilian'):
                continue
            
            if eve_type.id in bad_bpos:
                continue

            if eve_type is not None:
                activity_product_product = eve_type.industry_products.filter(activity_id=1).first()
                if not hasattr(activity_product_product, 'product_eve_type'):
                    continue
                activity_product_product = activity_product_product.product_eve_type

                if hasattr(activity_product_product, 'inv_meta_types') and activity_product_product.inv_meta_types != None and activity_product_product.inv_meta_types.meta_group_id != 1 and activity_product_product.inv_meta_types.meta_group_id != 54:
                    continue

            blueprint_view_model = owned_blueprints_blueprints()
            blueprint_view_model.blueprint_id = eve_type.id
            blueprint_view_model.blueprint_name = eve_type.name
            blueprint_view_model.base_cost = eve_type.base_price.base_price if hasattr(eve_type, 'base_price') and eve_type.base_price is not None else 0

            blueprint = owned_blueprints.filter(eve_type=eve_type).first()
            if blueprint:
                blueprint_view_model.owned_count = 1
            else:
                blueprint_view_model.owned_count = 0

            market_group_view_model.blueprints.append(blueprint_view_model)
        
        market_group_view_model.blueprint_count = len(market_group_view_model.blueprints)

        if len(market_group.market_group_children.all()) > 0:
            market_group_view_model.sub_groups = _market_cycler(market_group.market_group_children.all(), owned_blueprints)

        models.append(market_group_view_model)

    return models
