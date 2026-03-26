"""App Tasks"""

# Standard Library
import json
import logging
import urllib.request
from datetime import timedelta

# Third Party
from celery import shared_task
from django.utils import timezone
from esi.models import Token

from eve_sde.models import ItemType

from . import app_settings
from .helpers.esi import (
    get_character_blueprints,
    get_character_details,
    get_corporation_blueprints,
    get_corporation_details,
)
from .models import (
    CharacterBlueprint,
    CharacterBlueprintSync,
    CorporationBlueprint,
    CorporationBlueprintSync,
)

logger = logging.getLogger(__name__)


def _is_original_blueprint(quantity, runs):
    if runs in (None, -1):
        return True

    return quantity == -1


def _field_value(item, field_name, default=None):
    if isinstance(item, dict):
        return item.get(field_name, default)

    return getattr(item, field_name, default)


def _scoped_tokens_queryset():
    queryset = Token.objects.select_related("user")

    if hasattr(queryset, "require_valid"):
        queryset = queryset.require_valid()

    if hasattr(queryset, "require_scopes"):
        queryset = queryset.require_scopes([app_settings.WIZARDINDUSTRY_BLUEPRINT_SCOPE])
    else:
        queryset = queryset.filter(scopes__name=app_settings.WIZARDINDUSTRY_BLUEPRINT_SCOPE)

    return queryset.distinct()


def _corporation_scoped_tokens_queryset():
    queryset = Token.objects.select_related("user")

    if hasattr(queryset, "require_valid"):
        queryset = queryset.require_valid()

    if hasattr(queryset, "require_scopes"):
        queryset = queryset.require_scopes([app_settings.WIZARDINDUSTRY_CORPORATION_BLUEPRINT_SCOPE])
    else:
        queryset = queryset.filter(scopes__name=app_settings.WIZARDINDUSTRY_CORPORATION_BLUEPRINT_SCOPE)

    return queryset.distinct()


@shared_task
def sync_character_blueprints(token_id):
    try:
        token = Token.objects.select_related("user").get(id=token_id)
    except Token.DoesNotExist:
        return 0

    if token.user is None:
        return 0

    sync_state, _ = CharacterBlueprintSync.objects.get_or_create(
        user=token.user,
        character_id=token.character_id,
        defaults={"character_name": token.character_name},
    )

    now = timezone.now()
    item_ids_seen = set()

    try:
        blueprints = get_character_blueprints(token)

        for blueprint in blueprints:
            item_id = _field_value(blueprint, "item_id")
            type_id = _field_value(blueprint, "type_id")

            if item_id is None or type_id is None:
                continue

            eve_type = ItemType.objects.filter(id=type_id).first()
            if eve_type is None:
                continue

            quantity = _field_value(blueprint, "quantity")
            runs = _field_value(blueprint, "runs")

            CharacterBlueprint.objects.update_or_create(
                character_id=token.character_id,
                item_id=item_id,
                defaults={
                    "user": token.user,
                    "character_name": token.character_name,
                    "eve_type": eve_type,
                    "quantity": quantity,
                    "runs": runs,
                    "material_efficiency": _field_value(blueprint, "material_efficiency"),
                    "time_efficiency": _field_value(blueprint, "time_efficiency"),
                    "location_id": _field_value(blueprint, "location_id"),
                    "location_flag": _field_value(blueprint, "location_flag"),
                    "is_original": _is_original_blueprint(quantity, runs),
                    "last_synced_at": now,
                },
            )

            item_ids_seen.add(item_id)

        stale_query = CharacterBlueprint.objects.filter(
            user=token.user,
            character_id=token.character_id,
        )

        if item_ids_seen:
            stale_query.exclude(item_id__in=item_ids_seen).delete()
        else:
            stale_query.delete()

        sync_state.character_name = token.character_name
        sync_state.last_success_at = now
        sync_state.last_error = None
        sync_state.save(update_fields=["character_name", "last_success_at", "last_error", "updated_at"])

        return len(item_ids_seen)
    except Exception as ex:
        logger.exception("Failed syncing blueprints for character %s", token.character_id)
        sync_state.character_name = token.character_name
        sync_state.last_error = str(ex)[:1000]
        sync_state.save(update_fields=["character_name", "last_error", "updated_at"])

    return 0


@shared_task
def sync_all_character_blueprints():
    if not app_settings.WIZARDINDUSTRY_BLUEPRINT_SYNC_ENABLED:
        return 0

    now = timezone.now()
    max_per_run = max(1, int(app_settings.WIZARDINDUSTRY_BLUEPRINT_SYNC_MAX_PER_RUN))
    stale_after = now - timedelta(hours=int(app_settings.WIZARDINDUSTRY_BLUEPRINT_SYNC_CYCLE_HOURS))

    deduped_tokens = {}
    for token in _scoped_tokens_queryset():
        if token.character_id not in deduped_tokens:
            deduped_tokens[token.character_id] = token

    if not deduped_tokens:
        return 0

    tokens = list(deduped_tokens.values())
    user_ids = [token.user_id for token in tokens]
    character_ids = [token.character_id for token in tokens]

    sync_times = {
        (row["user_id"], row["character_id"]): row["last_success_at"]
        for row in CharacterBlueprintSync.objects.filter(
            user_id__in=user_ids,
            character_id__in=character_ids,
        ).values("user_id", "character_id", "last_success_at")
    }

    stale_tokens = []
    for token in tokens:
        last_success = sync_times.get((token.user_id, token.character_id))

        if last_success is None:
            stale_tokens.append((float("inf"), token))
            continue

        if last_success <= stale_after:
            stale_age = (now - last_success).total_seconds()
            stale_tokens.append((stale_age, token))

    if not stale_tokens:
        return 0

    stale_tokens.sort(key=lambda row: row[0], reverse=True)
    selected_tokens = [token for _, token in stale_tokens[:max_per_run]]

    synced = 0
    for token in selected_tokens:
        sync_character_blueprints(token.id)
        synced += 1

    return synced


@shared_task
def sync_corporation_blueprints(token_id):
    try:
        token = Token.objects.select_related("user").get(id=token_id)
    except Token.DoesNotExist:
        return 0

    if token.user is None:
        return 0

    try:
        character_info = get_character_details(token.character_id)
    except Exception:
        logger.exception("Failed resolving corporation for character %s", token.character_id)
        return 0

    corporation_id = _field_value(character_info, "corporation_id")
    if corporation_id is None:
        return 0

    corporation_name = None
    try:
        corporation_info = get_corporation_details(corporation_id)
        corporation_name = _field_value(corporation_info, "name")
    except Exception:
        logger.exception("Failed resolving corporation name for corporation %s", corporation_id)

    sync_state, _ = CorporationBlueprintSync.objects.get_or_create(
        user=token.user,
        corporation_id=corporation_id,
        defaults={
            "corporation_name": corporation_name,
            "character_id": token.character_id,
            "character_name": token.character_name,
        },
    )

    now = timezone.now()
    item_ids_seen = set()

    try:
        blueprints = get_corporation_blueprints(token, corporation_id)

        for blueprint in blueprints:
            item_id = _field_value(blueprint, "item_id")
            type_id = _field_value(blueprint, "type_id")

            if item_id is None or type_id is None:
                continue

            eve_type = ItemType.objects.filter(id=type_id).first()
            if eve_type is None:
                continue

            quantity = _field_value(blueprint, "quantity")
            runs = _field_value(blueprint, "runs")

            CorporationBlueprint.objects.update_or_create(
                user=token.user,
                corporation_id=corporation_id,
                item_id=item_id,
                defaults={
                    "corporation_name": corporation_name,
                    "eve_type": eve_type,
                    "quantity": quantity,
                    "runs": runs,
                    "material_efficiency": _field_value(blueprint, "material_efficiency"),
                    "time_efficiency": _field_value(blueprint, "time_efficiency"),
                    "location_id": _field_value(blueprint, "location_id"),
                    "location_flag": _field_value(blueprint, "location_flag"),
                    "is_original": _is_original_blueprint(quantity, runs),
                    "last_synced_at": now,
                },
            )

            item_ids_seen.add(item_id)

        stale_query = CorporationBlueprint.objects.filter(
            user=token.user,
            corporation_id=corporation_id,
        )

        if item_ids_seen:
            stale_query.exclude(item_id__in=item_ids_seen).delete()
        else:
            stale_query.delete()

        sync_state.corporation_name = corporation_name
        sync_state.character_id = token.character_id
        sync_state.character_name = token.character_name
        sync_state.last_success_at = now
        sync_state.last_error = None
        sync_state.save(
            update_fields=[
                "corporation_name",
                "character_id",
                "character_name",
                "last_success_at",
                "last_error",
                "updated_at",
            ]
        )

        return len(item_ids_seen)
    except Exception as ex:
        logger.exception("Failed syncing corporation blueprints for corporation %s", corporation_id)
        sync_state.corporation_name = corporation_name
        sync_state.character_id = token.character_id
        sync_state.character_name = token.character_name
        sync_state.last_error = str(ex)[:1000]
        sync_state.save(update_fields=["corporation_name", "character_id", "character_name", "last_error", "updated_at"])

    return 0


@shared_task
def sync_all_corporation_blueprints():
    if not app_settings.WIZARDINDUSTRY_CORPORATION_BLUEPRINT_SYNC_ENABLED:
        return 0

    now = timezone.now()
    max_per_run = max(1, int(app_settings.WIZARDINDUSTRY_CORPORATION_BLUEPRINT_SYNC_MAX_PER_RUN))
    stale_after = now - timedelta(hours=int(app_settings.WIZARDINDUSTRY_CORPORATION_BLUEPRINT_SYNC_CYCLE_HOURS))

    corporation_tokens = {}
    for token in _corporation_scoped_tokens_queryset():
        try:
            character_info = get_character_details(token.character_id)
            corporation_id = _field_value(character_info, "corporation_id")
            if corporation_id is None:
                continue
            key = (token.user_id, corporation_id)
            if key not in corporation_tokens:
                corporation_tokens[key] = token
        except Exception:
            logger.exception("Failed resolving corporation for character %s", token.character_id)

    if not corporation_tokens:
        return 0

    sync_times = {
        (row["user_id"], row["corporation_id"]): row["last_success_at"]
        for row in CorporationBlueprintSync.objects.filter(
            user_id__in=[key[0] for key in corporation_tokens.keys()],
            corporation_id__in=[key[1] for key in corporation_tokens.keys()],
        ).values("user_id", "corporation_id", "last_success_at")
    }

    stale_tokens = []
    for key, token in corporation_tokens.items():
        last_success = sync_times.get(key)

        if last_success is None:
            stale_tokens.append((float("inf"), token))
            continue

        if last_success <= stale_after:
            stale_age = (now - last_success).total_seconds()
            stale_tokens.append((stale_age, token))

    if not stale_tokens:
        return 0

    stale_tokens.sort(key=lambda row: row[0], reverse=True)
    selected_tokens = [token for _, token in stale_tokens[:max_per_run]]

    synced = 0
    for token in selected_tokens:
        sync_corporation_blueprints(token.id)
        synced += 1

    return synced
