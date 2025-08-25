"""App Tasks"""

# Standard Library
import json
import logging
import urllib.request

# Third Party
from celery import shared_task

# Alliance Auth (External Libs)
from eveuniverse.models import EveType

from .models import (
    BasePrice,
    CharacterAsset,
    CorporationAsset,
    EveLocation,
    invMetaTypes,
)

logger = logging.getLogger(__name__)


@shared_task
def get_base_prices():
    with urllib.request.urlopen("https://sde.eve-o.tech/latest/invTypes.json") as url:
        data = json.loads(url.read().decode())
        for item in data:
            if "basePrice" not in item or item["basePrice"] is None:
                continue
            try:
                eve_type = EveType.objects.get(id=item["typeID"])
                base_price, created = BasePrice.objects.get_or_create(eve_type=eve_type)
                base_price.base_price = item["basePrice"]
                base_price.save()
            except Exception:
                continue


@shared_task
def get_inv_meta_types():
    with urllib.request.urlopen(
        "https://sde.eve-o.tech/latest/invMetaTypes.json"
    ) as url:
        data = json.loads(url.read().decode())
        for item in data:
            try:
                eve_type = EveType.objects.get(id=item["typeID"])
                inv_meta_types, created = invMetaTypes.objects.get_or_create(
                    eve_type=eve_type
                )
                inv_meta_types.parent_type_id = item["parentTypeID"]
                inv_meta_types.meta_group_id = item["metaGroupID"]
                inv_meta_types.save()
            except Exception:
                continue


@shared_task
def _create_office_locations():
    corp_offices = CorporationAsset.objects.filter(location_flag="OfficeFolder").all()

    location_names = list(
        EveLocation.objects.all().values_list("location_id", flat=True)
    )

    for office in corp_offices:
        if office.item_id not in location_names:
            structure = EveLocation.objects.filter(
                location_id=office.location_id
            ).first()
            new_location = EveLocation(
                location_id=office.item_id,
                location_name=f"Office: #{office.item_id}",
                system_id=structure.system_id if structure else None,
            )
            new_location.save()


@shared_task
def _update_office_locations():
    location_names = EveLocation.objects.filter(
        location_name__startswith="Office", system_id__isnull=True
    ).all()

    location_names = list(
        EveLocation.objects.all().values_list("location_id", flat=True)
    )

    for location in location_names:
        asset = CorporationAsset.objects.filter(item_id=location.location_id).first()
        if not asset:
            continue

        if asset.location_id in location_names:
            location.location_name_id = asset.location_id
            location.save()


@shared_task
def _create_can_locations():
    expandable_categories = [2]
    not_groups = [14]

    corp_cans = (
        CorporationAsset.objects.filter(
            type_name__eve_group__eve_category_id__in=expandable_categories,
            singleton=True,
        )
        .exclude(type_name__eve_group__id__in=not_groups)
        .order_by("pk")
    )

    location_names = list(
        EveLocation.objects.all().values_list("location_id", flat=True)
    )

    for can in corp_cans:
        if can.item_id not in location_names:
            structure = EveLocation.objects.filter(location_id=can.location_id).first()
            new_location = EveLocation(
                location_id=can.item_id,
                location_name=f"Can: {can.name}",
                system_id=structure.system_id if structure else None,
            )
            new_location.save()


@shared_task
def _update_can_locations():
    location_names = EveLocation.objects.filter(location_name__startswith="Can:").all()

    location_names = list(
        EveLocation.objects.all().values_list("location_id", flat=True)
    )

    for location in location_names:
        asset = CorporationAsset.objects.filter(item_id=location.location_id).first()
        if not asset:
            asset = CharacterAsset.objects.filter(item_id=location.location_id).first()
            if not asset:
                continue

        if asset.location_id in location_names:
            location.location_name_id = asset.location_id
            location.location_name = f"Can: {asset.name}"
            location.save()
