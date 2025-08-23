# Standard Library
from typing import Union

# Third Party
from bravado.exception import HTTPForbidden

# Django
from django.contrib.auth.models import User
from django.db import models

# Alliance Auth
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from esi.errors import TokenError
from esi.models import Token

# Alliance Auth (External Libs)
from eveuniverse.models import EveSolarSystem, EveType

from .providers import esi

logger = get_extension_logger(__name__)


def get_token(character_id: int, scopes: list) -> "Token":
    """Helper method to get a valid token for a specific character with specific scopes.

    Args:
        character_id: Character to filter on.
        scopes: array of ESI scope strings to search for.

    Returns:
        Matching token or `False` when token is not found
    """
    token = (
        Token.objects.filter(character_id=character_id)
        .require_scopes(scopes)
        .require_valid()
        .first()
    )
    if token:
        return token
    else:
        return False


def get_corp_token(corp_id: int, scopes: list, req_roles: list | None | bool):
    """
    Helper method to get a token for a specific character from a specific corp with specific scopes, where
    a character has specific in game roles.
    :param corp_id: Corp to filter on.
    :param scopes: array of ESI scope strings required on the token
    :param req_roles: array of roles, one of which is required on the character.
    :return: :class:esi.models.Token or None
    """

    # always add roles scope as a requirement.
    if "esi-characters.read_corporation_roles.v1" not in scopes:
        scopes.append("esi-characters.read_corporation_roles.v1")

    # Find all characters in the corporation known to auth.
    char_ids = EveCharacter.objects.filter(corporation_id=corp_id).values(
        "character_id"
    )

    # find all tokens for the corp, with the scopes.
    tokens = Token.objects.filter(character_id__in=char_ids).require_scopes(scopes)

    # loop to check the roles and break on first correct match
    for token in tokens:
        try:
            if req_roles:  # There are endpoints with no requirements
                roles = esi.client.Character.get_characters_character_id_roles(
                    character_id=token.character_id, token=token.valid_access_token()
                ).result()

                has_roles = False

                # do we have the roles.
                for role in roles.get("roles", []):
                    if role in req_roles:
                        has_roles = True
                        break

                if has_roles:
                    return token  # return the token
                else:
                    pass  # next! TODO should we flag this character?
            else:
                return token  # no roles check needed return the token
        except TokenError as e:
            #  I've had invalid tokens in auth that refresh but don't actually work
            logger.error(f"Token Error ID: {token.pk} ({e})")

    return None


def fetch_location_name(location_id, location_flag, character_id, update=False):
    """Takes a location_id and character_id and returns a location model for items in a station/structure or in space"""

    accepted_location_flags = [
        "AssetSafety",
        "Deliveries",
        "Hangar",
        "HangarAll",
        "solar_system",
        "OfficeFolder",
        "CorpDeliveries",
        "AutoFit",
        "Impounded",
        "QuantumCoreRoom",
    ]

    if location_flag not in accepted_location_flags:
        if location_flag is not None:
            return None  # ship fits or in cargo holds or what ever also dont care

    existing = EveLocation.objects.filter(location_id=location_id)
    current_loc = existing.exists()

    if current_loc and location_id < 64000000:
        return existing.first()
    else:
        existing = existing.first()

    if location_id == 2004:
        # ASSET SAFETY
        return EveLocation(location_id=location_id, location_name="Asset Safety")
    elif 30000000 < location_id < 33000000:  # Solar System
        system = EveSolarSystem.objects.get_or_create_esi(id=location_id)
        if not system:
            logger.error("Unknown System, Have you populated the map?")
            return None
        else:
            system = system[0]
        return EveLocation(
            location_id=location_id, location_name=system.name, system=system
        )
    elif 60000000 < location_id < 64000000:  # Station ID
        station = esi.client.Universe.get_universe_stations_station_id(
            station_id=location_id
        ).result()
        system = EveSolarSystem.objects.get_or_create_esi(id=station.get("system_id"))
        if not system:
            logger.error("Unknown System, Have you populated the map?")
            return None
        return EveLocation(
            location_id=location_id,
            location_name=station.get("name"),
            system_id=station.get("system_id"),
        )

    req_scopes = ["esi-universe.read_structures.v1"]

    token = Token.get_token(character_id, req_scopes)

    if not token:
        return None

    else:
        try:
            structure = esi.client.Universe.get_universe_structures_structure_id(
                structure_id=location_id, token=token.valid_access_token()
            ).result()
        except HTTPForbidden as e:  # no access
            logger.debug(
                "Failed to get location:{}, Error:{}, Errors Remaining:{}, Time Remaining: {}".format(
                    location_id,
                    e.message,
                    e.response.headers.get("x-esi-error-limit-remain"),
                    e.response.headers.get("x-esi-error-limit-reset"),
                )
            )
            return None
        system = EveSolarSystem.objects.get_or_create_esi(
            id=structure.get("solar_system_id")
        )
        if not system:
            logger.error("Unknown System, Have you populated the map?")
            return None
        if current_loc:
            existing.location_name = structure.get("name")
            return existing
        else:
            return EveLocation(
                location_id=location_id,
                location_name=structure.get("name"),
                system_id=structure.get("solar_system_id"),
            )


class BasePrice(models.Model):
    """
    Base Price Model
    """

    eve_type = models.OneToOneField(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
        related_name="base_price",
        default=None,
    )
    base_price = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )


class invMetaTypes(models.Model):
    eve_type = models.OneToOneField(
        "eveuniverse.EveType",
        on_delete=models.CASCADE,
        related_name="inv_meta_types",
        default=None,
    )
    parent_type_id = models.IntegerField(null=True, blank=True)
    meta_group_id = models.IntegerField(null=True, blank=True)


class EveLocation(models.Model):
    location_id = models.BigIntegerField(primary_key=True)
    location_name = models.CharField(max_length=255)
    system = models.ForeignKey(
        EveSolarSystem, on_delete=models.SET_NULL, null=True, default=None
    )
    last_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.location_name}"


class Asset(models.Model):
    id = models.BigAutoField(primary_key=True)
    blueprint_copy = models.BooleanField(null=True, default=None)
    singleton = models.BooleanField()
    item_id = models.BigIntegerField()
    location_flag = models.CharField(max_length=50)
    location_id = models.BigIntegerField()
    location_type = models.CharField(max_length=25)
    quantity = models.IntegerField()
    type_id = models.IntegerField()
    type_name = models.ForeignKey(
        EveType, on_delete=models.SET_NULL, null=True, default=None
    )
    location_name = models.ForeignKey(
        EveLocation, on_delete=models.SET_NULL, null=True, default=None
    )

    name = models.CharField(max_length=255, null=True, default=None)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["location_id"]),
            models.Index(fields=["item_id"]),
        ]


class CharacterAsset(Asset):
    character = models.ForeignKey(
        CharacterOwnership, on_delete=models.deletion.CASCADE, related_name="+"
    )


class CorporationAsset(Asset):
    corporation = models.ForeignKey(
        EveCorporationInfo, on_delete=models.deletion.CASCADE, related_name="+"
    )


class Owner(models.Model):
    corporation = models.ForeignKey(
        EveCorporationInfo, on_delete=models.deletion.CASCADE, related_name="+"
    )
    character = models.ForeignKey(
        CharacterOwnership, on_delete=models.deletion.CASCADE, related_name="+"
    )

    corporation_owner = models.BooleanField(default=False)

    user = models.ForeignKey(User, on_delete=models.deletion.PROTECT, related_name="+")

    def _get_assets(self):
        if self.corporation_owner:
            self._get_corporation_assets()
            return
        else:
            self._get_character_assets()
            return

    def _get_character_assets(self):
        if self.corporation_owner:
            return False
        logger.debug(
            "Getting assets for owner: %s", self.character.character.character_name
        )

        required_scopes = ["esi-assets.read_assets.v1"]
        token = get_token(self.character.character.character_id, required_scopes)

        if not token:
            return False

        assets = esi.client.Assets.get_characters_character_id_assets(
            character_id=self.character.character.character_id,
            token=token.valid_access_token(),
        ).results()

        location_names = list(
            EveLocation.objects.all().values_list("location_id", flat=True)
        )

        item_ids = []
        items = []

        for item in assets:
            item_ids.append(item.get("item_id"))
            asset_item = CharacterAsset(
                character=self.character,
                blueprint_copy=item.get(" "),
                singleton=item.get("is_singleton"),
                item_id=item.get("item_id"),
                location_flag=item.get("location_flag"),
                location_id=item.get("location_id"),
                location_type=item.get("location_type"),
                quantity=item.get("quantity"),
                type_id=item.get("type_id"),
                type_name=item.get("type_name"),
                location_name=item.get("location_name"),
                name=item.get("name"),
            )

            if item.get("location_id") in location_names:
                asset_item.location_name_id = item.get("location_id")
            items.append(asset_item)

        delete_query = CharacterAsset.objects.filter(character=self.character)
        if delete_query.exists():
            delete_query.delete()

        CharacterAsset.objects.bulk_create(items)

    def _get_corporation_assets(self):
        if not self.corporation_owner:
            return False
        logger.debug("Getting assets for owner: %s", self.corporation.corporation_name)

        required_scopes = [
            "esi-assets.read_corporation_assets.v1",
            "esi-characters.read_corporation_roles.v1",
        ]
        required_roles = ["Director"]
        token = get_corp_token(
            self.corporation.corporation_id, required_scopes, required_roles
        )

        if not token:
            return False

        assets = esi.client.Assets.get_corporations_corporation_id_assets(
            corporation_id=self.corporation.corporation_id,
            token=token.valid_access_token(),
        ).results()

        location_names = list(
            EveLocation.objects.all().values_list("location_id", flat=True)
        )

        item_ids = []
        items = []
        failed_locations = []

        for item in assets:
            item_ids.append(item.get("item_id"))
            asset_item = CorporationAsset(
                corporation=self.corporation,
                blueprint_copy=item.get("is_blueprint_copy"),
                singleton=item.get("is_singleton"),
                item_id=item.get("item_id"),
                location_flag=item.get("location_flag"),
                location_id=item.get("location_id"),
                location_type=item.get("location_type"),
                quantity=item.get("quantity"),
                type_id=item.get("type_id"),
                type_name=item.get("type_name"),
                location_name=item.get("location_name"),
                name=item.get("name"),
            )

            if item.get("location_id") in location_names:
                asset_item.location_name_id = item.get("location_id")
            else:
                try:
                    if item.get("location_id") not in failed_locations:
                        new_name = fetch_location_name(
                            item.get("location_id"),
                            item.get("location_flag"),
                            token.character_id,
                        )
                        if new_name:
                            new_name.save()
                            location_names.append(item.get("location_id"))
                            asset_item.location_name_id = item.get("location_id")
                        else:
                            failed_locations.append(item.get("location_id"))
                except Exception as e:
                    raise e
                    pass
            items.append(asset_item)

        delete_query = CorporationAsset.objects.filter(corporation=self.corporation)
        if delete_query.exists():
            delete_query.delete()

        CorporationAsset.objects.bulk_create(items)
