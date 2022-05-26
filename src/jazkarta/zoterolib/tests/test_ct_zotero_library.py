# -*- coding: utf-8 -*-
from jazkarta.zoterolib.content.zotero_library import IZoteroLibrary
from jazkarta.zoterolib.testing import JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING
from jazkarta.zoterolib.testing import JAZKARTA_ZOTEROLIB_FUNCTIONAL_TESTING
from plone import api
from plone.app.testing import setRoles, TEST_USER_ID
from plone.dexterity.interfaces import IDexterityFTI

try:
    from plone.testing.zope import Browser
except ImportError:
    from plone.testing.z2 import Browser
from zope.component import createObject, queryUtility
from xml.sax.saxutils import escape

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

        item = ExternalZoteroItem(self.portal, TEST_ENTRY)
        self.assertTrue(item.Authors(), "Could not find the Authors field")
        self.assertEqual(item.Authors(), ", ".join(TEST_ENTRY["authors"]))
        self.assertEqual(item.AuthorItems(), TEST_ENTRY["authors"])


class ZoteroLibraryIndexTest(unittest.TestCase):

    layer = JAZKARTA_ZOTEROLIB_FUNCTIONAL_TESTING

    def setUp(self):
        """Create a Zotero Library object."""
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.parent = self.portal
        self.obj = api.content.create(
            container=self.portal,
            type="Zotero Library",
            id="zotero_library",
            zotero_id=9467580,
            zotero_library_type="user",
        )
        api.content.transition(obj=self.obj, transition="publish")

    def test_index_external_item(self):
        self.obj.index_element(TEST_ENTRY)
        catalog = api.portal.get_tool("portal_catalog")
        results = catalog.searchResults(getAuthors="Hathaway")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].Authors, ", ".join(TEST_ENTRY["authors"]))
        self.assertEqual(results[0].portal_type, "ExternalZoteroItem")

    def test_fetch_external_items(self):
        result = self.obj.fetch_items(start=1, limit=5)
        self.assertEqual(len(result), 5)

    def test_view_external_item(self):
        self.obj.index_element(TEST_ENTRY)
        catalog = api.portal.get_tool("portal_catalog")
        brain = catalog.searchResults(getAuthors="Hathaway")[0]
        # need a commit to make the content visible to test browser
        import transaction

        transaction.commit()
        browser = Browser(self.layer["app"])
        browser.handleErrors = False
        browser.open(brain.getURL())
        self.assertIn(
            '<h1 class="documentTitle">{}</h1>'.format(escape(TEST_ENTRY["title"])),
            browser.contents,
        )
        self.assertIn(
            '<p class="documentDescription">{}</p>'.format(
                escape(TEST_ENTRY["citationLabel"])
            ),
            browser.contents,
        )


TEST_ENTRY = {
    "id": "TESTZOTERO",
    "authors": ["Hathaway, S. R.", "McKinley, J. C."],
    "title": "A multiphasic personality schedule (Minnesota): I, Construction of the schedule.",
    "source": "Journal of Psychology",
    "publication_year": "1940",
    "citationLabel": "Hathaway, S. R., & McKinley, J. C. (1940). A multiphasic personality schedule (Minnesota): I, Construction of the schedule.",
}
