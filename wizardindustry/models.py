"""
App Models
Create your models in here
"""

# Django
from django.conf import settings
from django.db import models
from django.utils import timezone

# Alliance Auth (External Libs)
from eve_sde.models import ItemType


class CharacterBlueprint(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wizardindustry_character_blueprints")
    character_id = models.BigIntegerField(db_index=True)
    character_name = models.CharField(max_length=255, null=True, blank=True)
    item_id = models.BigIntegerField()
    eve_type = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name="wizardindustry_blueprint_owners")
    quantity = models.IntegerField(null=True, blank=True)
    runs = models.IntegerField(null=True, blank=True)
    material_efficiency = models.IntegerField(null=True, blank=True)
    time_efficiency = models.IntegerField(null=True, blank=True)
    location_id = models.BigIntegerField(null=True, blank=True)
    location_flag = models.CharField(max_length=100, null=True, blank=True)
    is_original = models.BooleanField(default=False, db_index=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["character_id", "item_id"], name="wizind_charbp_item_unique"),
        ]
        indexes = [
            models.Index(fields=["user", "character_id"], name="wizind_charbp_user_char_idx"),
            models.Index(fields=["user", "eve_type", "is_original"], name="wizind_charbp_owned_idx"),
        ]


class CharacterBlueprintSync(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wizardindustry_blueprint_syncs")
    character_id = models.BigIntegerField(db_index=True)
    character_name = models.CharField(max_length=255, null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "character_id"], name="wizind_chbsync_user_char_unique"),
        ]


class CorporationBlueprint(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wizardindustry_corporation_blueprints")
    corporation_id = models.BigIntegerField(db_index=True)
    corporation_name = models.CharField(max_length=255, null=True, blank=True)
    item_id = models.BigIntegerField()
    eve_type = models.ForeignKey(ItemType, on_delete=models.CASCADE, related_name="wizardindustry_corporation_blueprint_owners")
    quantity = models.IntegerField(null=True, blank=True)
    runs = models.IntegerField(null=True, blank=True)
    material_efficiency = models.IntegerField(null=True, blank=True)
    time_efficiency = models.IntegerField(null=True, blank=True)
    location_id = models.BigIntegerField(null=True, blank=True)
    location_flag = models.CharField(max_length=100, null=True, blank=True)
    is_original = models.BooleanField(default=False, db_index=True)
    last_synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "corporation_id", "item_id"], name="wizind_corpbp_item_unique"),
        ]
        indexes = [
            models.Index(fields=["user", "corporation_id"], name="wizind_corpbp_user_corp_idx"),
            models.Index(fields=["user", "eve_type", "is_original"], name="wizind_corpbp_owned_idx"),
        ]


class CorporationBlueprintSync(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wizardindustry_corporation_blueprint_syncs")
    corporation_id = models.BigIntegerField(db_index=True)
    corporation_name = models.CharField(max_length=255, null=True, blank=True)
    character_id = models.BigIntegerField(null=True, blank=True)
    character_name = models.CharField(max_length=255, null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "corporation_id"], name="wizind_corpsync_user_corp_unique"),
        ]
