# Standard Library
from unittest.mock import MagicMock, patch

# Django
from django.test import TestCase

# AA wizardindustry App
from wizardindustry.tasks import (
    _create_can_locations,
    _create_office_locations,
    _update_can_locations,
    _update_office_locations,
)


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


class UpdateOfficeLocationsTests(TestCase):
    def test_updates_location_when_asset_exists(self):
        mock_location = MagicMock()
        mock_location.location_id = 123

        mock_asset = MagicMock()
        mock_asset.location_id = 456

        with (
            patch("wizardindustry.tasks.EveLocation.objects") as mock_eve_locations,
            patch("wizardindustry.tasks.CorporationAsset.objects") as mock_corp_assets,
        ):
            mock_eve_locations.filter.return_value.all.return_value = [mock_location]
            mock_eve_locations.all.return_value.values_list.return_value = [123]
            mock_corp_assets.filter.return_value.first.return_value = mock_asset

            _update_office_locations()
            self.assertEqual(mock_location.location_name_id, mock_asset.location_id)
            mock_location.save.assert_called_once()

    def test_skips_location_when_no_asset(self):
        mock_location = MagicMock()
        mock_location.location_id = 123

        with (
            patch("wizardindustry.tasks.EveLocation.objects") as mock_eve_locations,
            patch("wizardindustry.tasks.CorporationAsset.objects") as mock_corp_assets,
        ):
            mock_eve_locations.filter.return_value.all.return_value = [mock_location]
            mock_eve_locations.all.return_value.values_list.return_value = [123]
            mock_corp_assets.filter.return_value.first.return_value = None

            _update_office_locations()
            self.assertFalse(hasattr(mock_location, "location_name_id"))
            mock_location.save.assert_not_called()


class UpdateCanLocationsTests(TestCase):
    def test_updates_location_with_corp_asset(self):
        mock_location = MagicMock()
        mock_location.location_id = 123

        mock_asset = MagicMock()
        mock_asset.location_id = 456
        mock_asset.name = "TestCan"

        with (
            patch("wizardindustry.tasks.EveLocation.objects") as mock_eve_locations,
            patch("wizardindustry.tasks.CorporationAsset.objects") as mock_corp_assets,
            patch("wizardindustry.tasks.CharacterAsset.objects") as mock_char_assets,
        ):
            mock_eve_locations.filter.return_value.all.return_value = [mock_location]
            mock_eve_locations.all.return_value.values_list.return_value = [123]
            mock_corp_assets.filter.return_value.first.return_value = mock_asset
            mock_char_assets.filter.return_value.first.return_value = None

            _update_can_locations()
            self.assertEqual(mock_location.location_name_id, mock_asset.location_id)
            self.assertEqual(mock_location.location_name, f"Can: {mock_asset.name}")
            mock_location.save.assert_called_once()

    def test_updates_location_with_char_asset(self):
        mock_location = MagicMock()
        mock_location.location_id = 123

        mock_asset = MagicMock()
        mock_asset.location_id = 456
        mock_asset.name = "CharCan"

        with (
            patch("wizardindustry.tasks.EveLocation.objects") as mock_eve_locations,
            patch("wizardindustry.tasks.CorporationAsset.objects") as mock_corp_assets,
            patch("wizardindustry.tasks.CharacterAsset.objects") as mock_char_assets,
        ):
            mock_eve_locations.filter.return_value.all.return_value = [mock_location]
            mock_eve_locations.all.return_value.values_list.return_value = [123]
            mock_corp_assets.filter.return_value.first.return_value = None
            mock_char_assets.filter.return_value.first.return_value = mock_asset

            _update_can_locations()
            self.assertEqual(mock_location.location_name_id, mock_asset.location_id)
            self.assertEqual(mock_location.location_name, f"Can: {mock_asset.name}")
            mock_location.save.assert_called_once()

    def test_skips_location_when_no_asset(self):
        mock_location = MagicMock()
        mock_location.location_id = 123

        with (
            patch("wizardindustry.tasks.EveLocation.objects") as mock_eve_locations,
            patch("wizardindustry.tasks.CorporationAsset.objects") as mock_corp_assets,
            patch("wizardindustry.tasks.CharacterAsset.objects") as mock_char_assets,
        ):
            mock_eve_locations.filter.return_value.all.return_value = [mock_location]
            mock_eve_locations.all.return_value.values_list.return_value = [123]
            mock_corp_assets.filter.return_value.first.return_value = None
            mock_char_assets.filter.return_value.first.return_value = None

            _update_can_locations()
            self.assertFalse(hasattr(mock_location, "location_name_id"))
            mock_location.save.assert_not_called()


class CreateCanLocationsTests(TestCase):
    def test_creates_new_can_location(self):
        mock_can = MagicMock()
        mock_can.item_id = 123
        mock_can.location_id = 456
        mock_can.name = "TestCan"

        mock_structure = MagicMock()
        mock_structure.system_id = 789

        with (
            patch("wizardindustry.tasks.CorporationAsset.objects") as mock_corp_assets,
            patch("wizardindustry.tasks.EveLocation.objects") as mock_eve_locations,
            patch("wizardindustry.tasks.EveLocation") as mock_eve_location_class,
        ):
            mock_corp_assets.filter.return_value.exclude.return_value.order_by.return_value = [
                mock_can
            ]
            mock_eve_locations.all.return_value.values_list.return_value = []
            mock_eve_locations.filter.return_value.first.return_value = mock_structure

            instance = MagicMock()
            mock_eve_location_class.return_value = instance

            _create_can_locations()
            mock_eve_location_class.assert_called_once_with(
                location_id=123, location_name="Can: TestCan", system_id=789
            )
            instance.save.assert_called_once()

    def test_skips_existing_can_location(self):
        mock_can = MagicMock()
        mock_can.item_id = 123
        mock_can.location_id = 456
        mock_can.name = "TestCan"

        with (
            patch("wizardindustry.tasks.CorporationAsset.objects") as mock_corp_assets,
            patch("wizardindustry.tasks.EveLocation.objects") as mock_eve_locations,
            patch("wizardindustry.tasks.EveLocation") as mock_eve_location_class,
        ):
            mock_corp_assets.filter.return_value.exclude.return_value.order_by.return_value = [
                mock_can
            ]
            mock_eve_locations.all.return_value.values_list.return_value = [123]

            _create_can_locations()
            mock_eve_location_class.assert_not_called()
