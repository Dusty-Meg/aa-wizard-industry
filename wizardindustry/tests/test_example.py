"""
wizardindustry Test
"""

# Django
from django.test import TestCase


class Testwizardindustry(TestCase):
    """
    Testwizardindustry
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Test setup
        :return:
        :rtype:
        """

        super().setUpClass()

    def test_wizardindustry(self):
        """
        Dummy test function
        :return:
        :rtype:
        """

        self.assertEqual(True, True)
