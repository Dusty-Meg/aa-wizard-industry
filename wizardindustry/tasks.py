"""App Tasks"""

# Standard Library
import json
import logging
import urllib.request

# Third Party
from celery import shared_task

# Alliance Auth (External Libs)
from eveuniverse.models import EveType

from .models import BasePrice, invMetaTypes

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
