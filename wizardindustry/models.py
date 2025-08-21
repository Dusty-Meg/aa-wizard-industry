"""
App Models
Create your models in here
"""

# Django
from django.db import models
from django.contrib.auth.models import Group, User

# Alliance Auth (External Libs)
from eveuniverse.models import EveType
from allianceauth.eveonline.models import EveCorporationInfo
from allianceauth.authentication.models import CharacterOwnership, State


class BasePrice(models.Model):
    """
    Base Price Model
    """
    eve_type = models.OneToOneField("eveuniverse.EveType", on_delete=models.CASCADE, related_name="base_price", default=None)
    base_price = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)


class invMetaTypes(models.Model):
    eve_type = models.OneToOneField("eveuniverse.EveType", on_delete=models.CASCADE, related_name="inv_meta_types", default=None)
    parent_type_id = models.IntegerField(null=True, blank=True)
    meta_group_id = models.IntegerField(null=True, blank=True)


class Owner(models.Model):
    corporation = models.ForeignKey(EveCorporationInfo, on_delete=models.deletion.CASCADE, related_name="+")
    character = models.ForeignKey(CharacterOwnership, on_delete=models.deletion.CASCADE, related_name="+")

    user = models.ForeignKey(User, on_delete=models.deletion.PROTECT, related_name="+")