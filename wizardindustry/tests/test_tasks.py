# Standard Library
from unittest.mock import MagicMock, patch

# Django
from django.test import TestCase

# AA wizardindustry App
from wizardindustry.tasks import _create_office_locations


class CreateOfficeLocationsTests(TestCase):
    def test_creates_new_location(self):
        mock_corp_office = MagicMock()
        mock_corp_office.item_id = 123
        mock_corp_office.location_id = 456

        mock_structure = MagicMock()
        mock_structure.system_id = 789

        with (
            patch("wizardindustry.tasks.CorporationAsset.objects") as mock_corp_assets,
            patch("wizardindustry.tasks.EveLocation") as mock_eve_location_class,
        ):
            # Setup EveLocation.objects
            mock_eve_locations = MagicMock()
            mock_eve_location_class.objects = mock_eve_locations

            mock_corp_assets.filter.return_value.all.return_value = [mock_corp_office]
            mock_eve_locations.all.return_value.values_list.return_value = []
            mock_eve_locations.filter.return_value.first.return_value = mock_structure

            instance = MagicMock()
            mock_eve_location_class.return_value = instance

            _create_office_locations()
            mock_eve_location_class.assert_called_once_with(
                location_id=123, location_name="Office: #123", system_id=789
            )
            instance.save.assert_called_once()

    def test_skips_existing_location(self):
        mock_corp_office = MagicMock()
        mock_corp_office.item_id = 123
        mock_corp_office.location_id = 456

        with (
            patch("wizardindustry.tasks.CorporationAsset.objects") as mock_corp_assets,
            patch("wizardindustry.tasks.EveLocation.objects") as mock_eve_locations,
        ):
            mock_corp_assets.filter.return_value.all.return_value = [mock_corp_office]
            mock_eve_locations.all.return_value.values_list.return_value = [123]
            _create_office_locations()
            # EveLocation should not be created
            mock_eve_locations.filter.assert_not_called()
