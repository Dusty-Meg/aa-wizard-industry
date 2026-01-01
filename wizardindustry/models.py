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
from esi.exceptions import HTTPNotModified
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
                roles = esi.client.Character.GetCharactersCharacterIdRoles(
                    character_id=token.character_id, token=token
                ).results(use_etag=False)

                has_roles = False

                # do we have the roles.
                for role in roles[0].roles:
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


def chunks(qst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, qst.count(), n):
        yield qst[i : i + n]


def fetch_location_name(
    location_id, location_flag, character_id, item_id, update=False
):
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
        station = esi.client.Universe.GetUniverseStationsStationId(
            station_id=location_id
        ).result()
        system = EveSolarSystem.objects.get_or_create_esi(id=station.system_id)
        if not system:
            logger.error("Unknown System, Have you populated the map?")
            return None
        return EveLocation(
            location_id=location_id,
            location_name=station.name,
            system_id=station.system_id,
        )
    elif location_flag == "OfficeFolder":
        structure = EveLocation.objects.filter(location_id=location_id).first()
        if not structure:
            structure = fetch_location_name(
                location_id, "Hangar", character_id, item_id
            )
            structure.save()
        return EveLocation(
            location_id=item_id,
            location_name=f"Office #{item_id}",
            system_id=structure.system_id if structure else None,
        )

    req_scopes = ["esi-universe.read_structures.v1"]

    token = Token.get_token(character_id, req_scopes)

    if not token:
        return None

    else:
        try:
            structure = esi.client.Universe.GetUniverseStructuresStructureId(
                structure_id=location_id, token=token
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
        system = EveSolarSystem.objects.get_or_create_esi(id=structure.solar_system_id)
        if not system:
            logger.error("Unknown System, Have you populated the map?")
            return None
        if current_loc:
            existing.location_name = structure.name
            return existing
        else:
            return EveLocation(
                location_id=location_id,
                location_name=structure.name,
                system_id=structure.solar_system_id,
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


class CorporationIndustryJob(models.Model):
    corporation = models.ForeignKey(
        EveCorporationInfo, on_delete=models.deletion.CASCADE, related_name="+"
    )

    activity_id = models.IntegerField()
    blueprint_id = models.BigIntegerField()
    blueprint_location_id = models.BigIntegerField()
    blueprint_type_id = models.BigIntegerField()
    blueprint_type_name = models.ForeignKey(
        EveType, on_delete=models.SET_NULL, null=True, default=None, related_name="+"
    )
    completed_character_id = models.BigIntegerField(null=True, default=None, blank=True)
    completed_date = models.DateTimeField(null=True, default=None, blank=True)
    cost = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, default=None, blank=True
    )
    duration = models.IntegerField()
    end_date = models.DateTimeField()
    facility_id = models.BigIntegerField()
    installer_id = models.BigIntegerField()
    job_id = models.IntegerField(primary_key=True)
    licensed_runs = models.IntegerField(null=True, default=None, blank=True)
    location_id = models.BigIntegerField()
    output_location_id = models.BigIntegerField()
    pause_date = models.DateTimeField(null=True, default=None, blank=True)
    probability = models.FloatField(null=True, default=None, blank=True)
    product_type_id = models.IntegerField()
    product_type_name = models.ForeignKey(
        EveType, on_delete=models.SET_NULL, null=True, default=None, related_name="+"
    )
    runs = models.IntegerField()
    start_date = models.DateTimeField()
    status = models.CharField(max_length=15)
    successful_runs = models.IntegerField(null=True, default=None, blank=True)

    blueprint_location_name = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        related_name="+",
    )
    facility_name = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        related_name="+",
    )
    output_location_name = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        related_name="+",
    )


class CharacterIndustryJob(models.Model):
    character = models.ForeignKey(CharacterOwnership, on_delete=models.CASCADE)

    activity_id = models.IntegerField()
    blueprint_id = models.BigIntegerField()
    blueprint_location_id = models.BigIntegerField()
    blueprint_type_id = models.BigIntegerField()
    blueprint_type_name = models.ForeignKey(
        EveType, on_delete=models.SET_NULL, null=True, default=None, related_name="+"
    )
    completed_character_id = models.BigIntegerField(default=None, null=True, blank=True)
    completed_date = models.DateTimeField(default=None, null=True, blank=True)
    cost = models.DecimalField(
        max_digits=20, decimal_places=2, default=None, null=True, blank=True
    )
    duration = models.IntegerField()
    end_date = models.DateTimeField()
    facility_id = models.BigIntegerField()
    installer_id = models.BigIntegerField()
    job_id = models.IntegerField()
    licensed_runs = models.IntegerField(default=None, null=True, blank=True)
    output_location_id = models.BigIntegerField()
    pause_date = models.DateTimeField(default=None, null=True, blank=True)
    probability = models.FloatField(default=None, null=True, blank=True)
    product_type_id = models.IntegerField()
    product_type_name = models.ForeignKey(
        EveType, on_delete=models.SET_NULL, null=True, default=None, related_name="+"
    )
    runs = models.IntegerField()
    start_date = models.DateTimeField()
    station_id = models.BigIntegerField()
    status = models.CharField(max_length=15)
    successful_runs = models.IntegerField(default=None, null=True, blank=True)

    blueprint_location_name = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        related_name="+",
    )
    facility_name = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        related_name="+",
    )
    output_location_name = models.ForeignKey(
        EveLocation,
        on_delete=models.SET_NULL,
        null=True,
        default=None,
        related_name="+",
    )


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
    system = models.ForeignKey(
        EveSolarSystem, on_delete=models.SET_NULL, null=True, default=None
    )

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

    def _get_industry_jobs(self):
        if self.corporation_owner:
            self._get_corporation_jobs()
            return
        else:
            self._get_character_jobs()
            return

    def _get_character_jobs(self):
        if self.corporation_owner:
            return False
        logger.debug(
            "Getting industry jobs for owner: %s",
            self.character.character.character_name,
        )

        required_scopes = ["esi-industry.read_character_jobs.v1"]
        token = get_token(self.character.character.character_id, required_scopes)

        if not token:
            return False

        jobs = esi.client.Industry.GetCharactersCharacterIdIndustryJobs(
            character_id=self.character.character.character_id,
            token=token,
        ).results()

        location_names = list(
            EveLocation.objects.all().values_list("location_id", flat=True)
        )

        existing_jobs = CharacterIndustryJob.objects.filter(
            character=self.character, job_id__in=[item.job_id for item in jobs]
        ).values_list("job_id", flat=True)

        item_ids = []
        items = []
        for item in jobs:
            item_ids.append(item.job_id)

            if item.job_id in existing_jobs:
                job_item = CharacterIndustryJob.objects.get(
                    character=self.character, job_id=item.job_id
                )
                job_item.completed_character_id = item.completed_character_id
                job_item.completed_date = item.completed_date
                job_item.end_date = item.end_date
                job_item.pause_date = item.pause_date
                job_item.status = item.status
                job_item.successful_runs = item.successful_runs

                if item.blueprint_location_id in location_names:
                    job_item.blueprint_location_name_id = item.blueprint_location_id
                if item.facility_id in location_names:
                    job_item.facility_name_id = item.facility_id
                if item.output_location_id in location_names:
                    job_item.output_location_name_id = item.output_location_id
                job_item.save()
                continue

            job_item = CharacterIndustryJob(
                character=self.character,
                activity_id=item.activity_id,
                blueprint_id=item.blueprint_id,
                blueprint_location_id=item.blueprint_location_id,
                blueprint_type_id=item.blueprint_type_id,
                blueprint_type_name=EveType.objects.get_or_create_esi(
                    id=item.blueprint_type_id
                )[0],
                completed_character_id=item.completed_character_id,
                completed_date=item.completed_date,
                cost=item.cost,
                duration=item.duration,
                end_date=item.end_date,
                facility_id=item.facility_id,
                installer_id=item.installer_id,
                job_id=item.job_id,
                licensed_runs=item.licensed_runs,
                output_location_id=item.output_location_id,
                pause_date=item.pause_date,
                probability=item.probability,
                product_type_id=item.product_type_id,
                product_type_name=EveType.objects.get_or_create_esi(
                    id=item.product_type_id
                )[0],
                runs=item.runs,
                start_date=item.start_date,
                station_id=item.station_id,
                status=item.status,
                successful_runs=item.successful_runs,
            )
            if item.blueprint_location_id in location_names:
                job_item.blueprint_location_name_id = item.blueprint_location_id
            if item.facility_id in location_names:
                job_item.facility_name_id = item.facility_id
            if item.output_location_id in location_names:
                job_item.output_location_name_id = item.output_location_id
            items.append(job_item)

        CharacterIndustryJob.objects.bulk_create(items)

    def _get_corporation_jobs(self):
        if not self.corporation_owner:
            return False
        logger.debug(
            "Getting industry jobs for owner: %s", self.corporation.corporation_name
        )

        required_scopes = [
            "esi-industry.read_corporation_jobs.v1",
            "esi-characters.read_corporation_roles.v1",
        ]
        required_roles = ["Factory_Manager"]
        token = get_corp_token(
            self.corporation.corporation_id, required_scopes, required_roles
        )

        if not token:
            return False

        jobs = esi.client.Industry.GetCorporationsCorporationIdIndustryJobs(
            corporation_id=self.corporation.corporation_id,
            token=token,
        ).results()

        location_names = list(
            EveLocation.objects.all().values_list("location_id", flat=True)
        )

        existing_jobs = CorporationIndustryJob.objects.filter(
            corporation=self.corporation,
            job_id__in=[item.job_id for item in jobs],
        ).values_list("job_id", flat=True)

        item_ids = []
        items = []
        for item in jobs:
            item_ids.append(item.job_id)

            if item.job_id in existing_jobs:
                job_item = CorporationIndustryJob.objects.get(
                    corporation=self.corporation, job_id=item.job_id
                )
                job_item.completed_character_id = item.completed_character_id
                job_item.completed_date = item.completed_date
                job_item.end_date = item.end_date
                job_item.pause_date = item.pause_date
                job_item.status = item.status
                job_item.successful_runs = item.successful_runs
                if item.blueprint_location_id in location_names:
                    job_item.blueprint_location_name_id = item.blueprint_location_id
                if item.facility_id in location_names:
                    job_item.facility_name_id = item.facility_id
                if item.output_location_id in location_names:
                    job_item.output_location_name_id = item.output_location_id

                job_item.save()
                continue

            job_item = CorporationIndustryJob(
                corporation=self.corporation,
                activity_id=item.activity_id,
                blueprint_id=item.blueprint_id,
                blueprint_location_id=item.blueprint_location_id,
                blueprint_type_id=item.blueprint_type_id,
                blueprint_type_name=EveType.objects.get_or_create_esi(
                    id=item.blueprint_type_id
                )[0],
                completed_character_id=item.completed_character_id,
                completed_date=item.completed_date,
                cost=item.cost,
                duration=item.duration,
                end_date=item.end_date,
                facility_id=item.facility_id,
                installer_id=item.installer_id,
                job_id=item.job_id,
                licensed_runs=item.licensed_runs,
                location_id=item.location_id,
                output_location_id=item.output_location_id,
                pause_date=item.pause_date,
                probability=item.probability,
                product_type_id=item.product_type_id,
                product_type_name=EveType.objects.get_or_create_esi(
                    id=item.product_type_id
                )[0],
                runs=item.runs,
                start_date=item.start_date,
                status=item.status,
                successful_runs=item.successful_runs,
            )
            if item.blueprint_location_id in location_names:
                job_item.blueprint_location_name_id = item.blueprint_location_id
            if item.facility_id in location_names:
                job_item.facility_name_id = item.facility_id
            if item.output_location_id in location_names:
                job_item.output_location_name_id = item.output_location_id

            items.append(job_item)

        CorporationIndustryJob.objects.bulk_create(items)

    def _get_assets(self):
        if self.corporation_owner:
            self._get_corporation_assets()
            self._update_corporation_asset_names()
            return
        else:
            self._get_character_assets()
            self._update_character_asset_names()
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

        try:
            assets = esi.client.Assets.GetCharactersCharacterIdAssets(
                character_id=self.character.character.character_id,
                token=token,
            ).results(use_etag=False)
        except HTTPNotModified:
            return

        locations = EveLocation.objects.all()

        location_names = list(
            EveLocation.objects.all().values_list("location_id", flat=True)
        )

        item_ids = []
        items = []

        for item in assets:
            item_ids.append(item.item_id)
            asset_item = CharacterAsset(
                character=self.character,
                blueprint_copy=item.is_blueprint_copy,
                singleton=item.is_singleton,
                item_id=item.item_id,
                location_flag=item.location_flag,
                location_id=item.location_id,
                location_type=item.location_type,
                quantity=item.quantity,
                type_id=item.type_id,
                type_name=EveType.objects.get_or_create_esi(id=item.type_id)[0],
            )

            if item.location_id in location_names:
                asset_item.location_name_id = item.location_id
                asset_item.system_id = locations.get(location_id=item.location_id).system_id
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

        try:
            assets = esi.client.Assets.GetCorporationsCorporationIdAssets(
                corporation_id=self.corporation.corporation_id,
                token=token,
            ).results(use_etag=False)
        except HTTPNotModified:
            return

        location_names = list(
            EveLocation.objects.all().values_list("location_id", flat=True)
        )
        locations = EveLocation.objects.all()

        item_ids = []
        items = []
        failed_locations = []

        for item in assets:
            item_ids.append(item.item_id)
            asset_item = CorporationAsset(
                corporation=self.corporation,
                blueprint_copy=item.is_blueprint_copy,
                singleton=item.is_singleton,
                item_id=item.item_id,
                location_flag=item.location_flag,
                location_id=item.location_id,
                location_type=item.location_type,
                quantity=item.quantity,
                type_id=item.type_id,
                type_name=EveType.objects.get_or_create_esi(id=item.type_id)[0],
                # location_name=item.location_name,
                # name=item.name,
            )

            if item.location_id in location_names:
                asset_item.location_name_id = item.location_id
                asset_item.system_id = locations.get(location_id=item.location_id).system_id
            else:
                try:
                    if (
                        item.location_id not in failed_locations
                        or item.location_flag == "OfficeFolder"
                    ):
                        new_name = fetch_location_name(
                            item.location_id,
                            item.location_flag,
                            token.character_id,
                            item.item_id,
                        )
                        if new_name:
                            new_name.save()
                            location_names.append(new_name.location_id)
                            locations = list(locations) + [new_name]
                            asset_item.location_name_id = new_name.location_id
                        else:
                            failed_locations.append(item.location_id)
                except Exception:
                    failed_locations.append(item.location_id)
                    pass
            items.append(asset_item)

        delete_query = CorporationAsset.objects.filter(corporation=self.corporation)
        if delete_query.exists():
            delete_query.delete()

        CorporationAsset.objects.bulk_create(items)

    def _update_corporation_asset_names(self):
        if not self.corporation_owner:
            return False
        logger.debug(
            "Getting asset names for owner: %s", self.corporation.corporation_name
        )

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
        expandable_categories = [2, 6, 65]
        assets = CorporationAsset.objects.filter(
            corporation=self.corporation,
            type_name__eve_group__eve_category_id__in=expandable_categories,
            singleton=True,
        ).order_by("pk")

        for subset in chunks(assets, 100):
            assets_names = esi.client.Assets.PostCorporationsCorporationIdAssetsNames(
                corporation_id=self.corporation.corporation_id,
                token=token,
                body=[item.item_id for item in subset],
            ).result()

            id_list = {i.item_id: i.name for i in assets_names}

            for asset in subset:
                if asset.item_id in id_list:
                    asset.name = id_list.get(asset.item_id)
                    asset.save()

    def _update_character_asset_names(self):
        if self.corporation_owner:
            return False
        logger.debug(
            "Getting asset names for owner: %s", self.character.character.character_name
        )

        required_scopes = [
            "esi-assets.read_assets.v1",
        ]

        token = get_token(self.character.character.character_id, required_scopes)
        if not token:
            return False
        expandable_categories = [2, 6, 65]
        assets = CharacterAsset.objects.filter(
            character=self.character,
            type_name__eve_group__eve_category_id__in=expandable_categories,
        ).order_by("pk")

        for subset in chunks(assets, 100):
            assets_names = esi.client.Assets.PostCharactersCharacterIdAssetsNames(
                character_id=self.character.character.character_id,
                token=token,
                body=[item.item_id for item in subset],
            ).result()

            id_list = {i.item_id: i.name for i in assets_names}

            for asset in subset:
                if asset.item_id in id_list:
                    asset.name = id_list.get(asset.item_id)
                    asset.save()
