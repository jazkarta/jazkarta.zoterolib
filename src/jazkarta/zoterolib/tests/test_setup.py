# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from jazkarta.zoterolib.testing import (
    JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING  # noqa: E501,,
)
from plone import api
from plone.app.testing import setRoles, TEST_USER_ID

import unittest


try:
    from Products.CMFPlone.utils import get_installer
except ImportError:
    get_installer = None


class TestSetup(unittest.TestCase):
    """Test that jazkarta.zoterolib is properly installed."""

    layer = JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        if get_installer:
            self.installer = get_installer(self.portal, self.layer['request'])
        else:
            self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if jazkarta.zoterolib is installed."""
        self.assertTrue(self.installer.isProductInstalled(
            'jazkarta.zoterolib'))

    def test_browserlayer(self):
        """Test that IJazkartaZoterolibLayer is registered."""
        from jazkarta.zoterolib.interfaces import (
            IJazkartaZoterolibLayer)
        from plone.browserlayer import utils
        self.assertIn(
            IJazkartaZoterolibLayer,
            utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        if get_installer:
            self.installer = get_installer(self.portal, self.layer['request'])
        else:
            self.installer = api.portal.get_tool('portal_quickinstaller')
        roles_before = api.user.get_roles(TEST_USER_ID)
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.installer.uninstallProducts(['jazkarta.zoterolib'])
        setRoles(self.portal, TEST_USER_ID, roles_before)

    def test_product_uninstalled(self):
        """Test if jazkarta.zoterolib is cleanly uninstalled."""
        self.assertFalse(self.installer.isProductInstalled(
            'jazkarta.zoterolib'))

    def test_browserlayer_removed(self):
        """Test that IJazkartaZoterolibLayer is removed."""
        from jazkarta.zoterolib.interfaces import \
            IJazkartaZoterolibLayer
        from plone.browserlayer import utils
        self.assertNotIn(
            IJazkartaZoterolibLayer,
            utils.registered_layers())
