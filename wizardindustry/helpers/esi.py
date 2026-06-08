# django-esi
from esi.openapi_clients import ESIClientProvider as ESIOpenApiProvider

from wizardindustry import __title__, __version__

esi_blueprints = ESIOpenApiProvider(
    ua_appname=__title__,
    ua_version=__version__,
    compatibility_date="2026-05-19",
    operations=[
        "GetCharactersCharacterIdBlueprints",
        "GetCharactersCharacterId",
        "GetCorporationsCorporationId",
        "GetCorporationsCorporationIdBlueprints"
    ]
)


def get_character_blueprints(token):
    operation = esi_blueprints.client.Character.GetCharactersCharacterIdBlueprints(
        character_id=token.character_id,
        token=token.valid_access_token(),
    )

    return operation.results()


def get_character_details(character_id):
    operation = esi_blueprints.client.Character.GetCharactersCharacterId(
        character_id=character_id,
    )

    return operation.result()


def get_corporation_details(corporation_id):
    operation = esi_blueprints.client.Corporation.GetCorporationsCorporationId(
        corporation_id=corporation_id,
    )

    return operation.result()


def get_corporation_blueprints(token, corporation_id):
    operation = esi_blueprints.client.Corporation.GetCorporationsCorporationIdBlueprints(
        corporation_id=corporation_id,
        token=token.valid_access_token(),
    )

    return operation.results()
