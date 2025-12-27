# Standard Library
import os

# Alliance Auth
from esi.openapi_clients import ESIClientProvider

from . import __version__

esi = ESIClientProvider(
    compatibility_date="2025-12-16",
    ua_appname="aa-wizard-industry",
    ua_version=__version__,
    operations=[
        "GetCharactersCharacterIdRoles",
        "GetUniverseStationsStationId",
        "GetUniverseStructuresStructureId",
        "GetCharactersCharacterIdIndustryJobs",
        "GetCorporationsCorporationIdIndustryJobs",
        "GetCharactersCharacterIdAssets",
        "GetCorporationsCorporationIdAssets",
        "PostCorporationsCorporationIdAssetsNames",
        "PostCharactersCharacterIdAssetsNames",
    ],
)
