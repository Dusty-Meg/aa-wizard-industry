# django-esi
from esi.clients import EsiClientProvider

from wizardindustry import __title__, __version__

esi_blueprints = EsiClientProvider(
    ua_appname=__title__,
    ua_version=__version__,
)


def get_character_blueprints(token):
    operation = esi_blueprints.client.Character.get_characters_character_id_blueprints(
        character_id=token.character_id,
        token=token.valid_access_token(),
    )

    return operation.results()


def get_character_details(character_id):
    operation = esi_blueprints.client.Character.get_characters_character_id(
        character_id=character_id,
    )

    return operation.result()


def get_corporation_details(corporation_id):
    operation = esi_blueprints.client.Corporation.get_corporations_corporation_id(
        corporation_id=corporation_id,
    )

    return operation.result()


def get_corporation_blueprints(token, corporation_id):
    operation = esi_blueprints.client.Corporation.get_corporations_corporation_id_blueprints(
        corporation_id=corporation_id,
        token=token.valid_access_token(),
    )

    return operation.results()
