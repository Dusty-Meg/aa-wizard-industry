"""
App Models
Create your models in here
"""

# Django
from django.db import models

# Alliance Auth (External Libs)
from eveuniverse.models import EveType


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