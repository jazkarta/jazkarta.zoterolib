# -*- coding: utf-8 -*-
from jazkarta.zoterolib.content.zotero_library import IZoteroLibrary  # NOQA E501
from jazkarta.zoterolib.testing import JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING  # noqa
from plone import api
from plone.app.testing import setRoles, TEST_USER_ID
from plone.dexterity.interfaces import IDexterityFTI
from zope.component import createObject, queryUtility

import unittest


class ZoteroLibraryIntegrationTest(unittest.TestCase):

    layer = JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.parent = self.portal

    def test_ct_zotero_library_schema(self):
        fti = queryUtility(IDexterityFTI, name="Zotero Library")
        schema = fti.lookupSchema()
        self.assertEqual(IZoteroLibrary, schema)

    def test_ct_zotero_library_fti(self):
        fti = queryUtility(IDexterityFTI, name="Zotero Library")
        self.assertTrue(fti)

    def test_ct_zotero_library_factory(self):
        fti = queryUtility(IDexterityFTI, name="Zotero Library")
        factory = fti.factory
        obj = createObject(factory)

        self.assertTrue(
            IZoteroLibrary.providedBy(obj),
            "IZoteroLibrary not provided by {0}!".format(
                obj,
            ),
        )

    def test_ct_zotero_library_adding(self):
        setRoles(self.portal, TEST_USER_ID, ["Contributor"])
        obj = api.content.create(
            container=self.portal,
            type="Zotero Library",
            id="zotero_library",
        )

        self.assertTrue(
            IZoteroLibrary.providedBy(obj),
            "IZoteroLibrary not provided by {0}!".format(
                obj.id,
            ),
        )

        parent = obj.__parent__
        self.assertIn("zotero_library", parent.objectIds())

        # check that deleting the object works too
        api.content.delete(obj=obj)
        self.assertNotIn("zotero_library", parent.objectIds())

    def test_ct_zotero_library_globally_addable(self):
        setRoles(self.portal, TEST_USER_ID, ["Contributor"])
        fti = queryUtility(IDexterityFTI, name="Zotero Library")
        self.assertTrue(fti.global_allow, "{0} is not globally addable!".format(fti.id))

    def test_external_item(self):
        from jazkarta.zoterolib.content.zotero_library import ExternalZoteroItem

        item = ExternalZoteroItem(TEST_ENTRY)
        self.assertTrue(item.Authors(), "Could not find the Authors field")
        self.assertEqual(item.Authors(), ", ".join(TEST_ENTRY["authors"]))
        self.assertEqual(item.AuthorItems(), TEST_ENTRY["authors"])


class ZoteroLibraryIndexTest(unittest.TestCase):

    layer = JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING

    def setUp(self):
        """Create a Zotero Library object."""
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.parent = self.portal
        self.obj = api.content.create(
            container=self.portal,
            type="Zotero Library",
            id="zotero_library",
        )

    def test_index_external_item(self):
        from jazkarta.zoterolib.content.zotero_library import ExternalZoteroItem

        self.obj.index_element(TEST_ENTRY)
        catalog = api.portal.get_tool("portal_catalog")
        results = catalog.search(query={"SearchableText": "Hathaway"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].Authors, ", ".join(TEST_ENTRY["authors"]))


TEST_ENTRY = {
    "id": "TESTZOTERO",
    "authors": ["Hathaway, S. R.", "McKinley, J. C."],
    "title": "A multiphasic personality schedule (Minnesota): I, Construction of the schedule.",
    "source": "Journal of Psychology",
    "publication_year": "1940",
    "citationLabel": "Hathaway, S. R., & McKinley, J. C. (1940). A multiphasic personality schedule (Minnesota): I, Construction of the schedule.",
}
