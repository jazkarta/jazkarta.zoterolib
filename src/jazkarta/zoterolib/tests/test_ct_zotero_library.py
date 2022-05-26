# -*- coding: utf-8 -*-
from itertools import islice
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
        self.assertEqual(item.Authors(), "Martin Sellbom, R Michael")
        self.assertEqual(item.AuthorItems(), ["Martin Sellbom", "R Michael"])


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
        results = catalog.searchResults(getAuthors="Sellbom")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].Authors, "Martin Sellbom, R Michael")
        self.assertEqual(results[0].portal_type, "ExternalZoteroItem")

    def test_fetch_external_items(self):
        result_iterator = self.obj.fetch_items(start=1, limit=5)
        result = tuple(islice(result_iterator, 5))
        self.assertEqual(len(result), 5)

    def test_fetch_and_index_external_items(self):
        result = self.obj.fetch_and_index_items()

    def test_view_external_item(self):
        self.obj.index_element(TEST_ENTRY)
        catalog = api.portal.get_tool("portal_catalog")
        brain = catalog.searchResults(getAuthors="Sellbom")[0]
        # need a commit to make the content visible to test browser
        import transaction

        transaction.commit()
        browser = Browser(self.layer["app"])
        browser.handleErrors = False
        browser.open(brain.getURL())
        self.assertIn(
            '<h1 class="documentTitle">{}</h1>'.format(
                escape(TEST_ENTRY["data"]["title"])
            ),
            browser.contents,
        )
        self.assertIn(
            '<p class="documentDescription">Psychological Assessment - Detection of overreported psychopathology with the MMPI-2 RF form validity scales</p>',
            browser.contents,
        )


TEST_ENTRY = {
    "data": {
        "DOI": "10.1037/a0020825",
        "ISSN": "1939-134X(Electronic);1040-3590(Print)",
        "abstractNote": "[Correction Notice: An erratum for this article was reported in Vol 23(1) of Psychological Assessment (see record 2011-01446-001). There was an error in the title. The title should "
        "have read “Detection of Overreported Psychopathology With the MMPI-2-RF Validity Scales.”] [Correction Notice: An erratum for this article was reported in Psychological Assessment "
        "(see record 2011-01446-001). There was an error in the title. The title should have read “Detection of Overreported Psychopathology With the MMPI-2-RF Validity Scales.”] We examined "
        "the utility of the validity scales on the recently released Minnesota Multiphasic Personality Inventory–2 Restructured Form (MMPI-2 RF; Ben-Porath & Tellegen, 2008) to detect "
        "overreported psychopathology. This set of validity scales includes a newly developed scale and revised versions of the original MMPI-2 validity scales. We used an analogue, "
        "experimental simulation in which MMPI-2 RF responses (derived from archived MMPI-2 protocols) of undergraduate students instructed to overreport psychopathology (in either a coached "
        "or noncoached condition) were compared with those of psychiatric inpatients who completed the MMPI-2 under standardized instructions. The MMPI-2 RF validity scale Infrequent "
        "Psychopathology Responses best differentiated the simulation groups from the sample of patients, regardless of experimental condition. No other validity scale added consistent "
        "incremental predictive utility to Infrequent Psychopathology Responses in distinguishing the simulation groups from the sample of patients. Classification accuracy statistics "
        "confirmed the recommended cut scores in the MMPI-2 RF manual (Ben-Porath & Tellegen, 2008).",
        "accessDate": "",
        "archive": "",
        "archiveLocation": "",
        "callNumber": "",
        "collections": ["X36527B6"],
        "creators": [
            {"creatorType": "author", "firstName": "Martin", "lastName": "Sellbom"},
            {"creatorType": "author", "firstName": "R", "lastName": "Michael"},
        ],
        "date": "2010",
        "dateAdded": "2022-05-02T20:50:24Z",
        "dateModified": "2022-05-02T20:50:24Z",
        "extra": "",
        "issue": "4",
        "itemType": "journalArticle",
        "journalAbbreviation": "",
        "key": "J8QG2849",
        "language": "",
        "libraryCatalog": "",
        "pages": "757–767",
        "publicationTitle": "Psychological Assessment",
        "relations": {},
        "rights": "",
        "series": "",
        "seriesText": "",
        "seriesTitle": "",
        "shortTitle": "",
        "tags": [],
        "title": "Detection of overreported psychopathology with the MMPI-2 RF form validity scales",
        "url": "",
        "version": 1818,
        "volume": "22",
    },
    "key": "J8QG2849",
    "library": {
        "id": 9467580,
        "links": {
            "alternate": {
                "href": "https://www.zotero.org/testdivision",
                "type": "text/html",
            }
        },
        "name": "UMP Test Division",
        "type": "user",
    },
    "links": {
        "alternate": {
            "href": "https://www.zotero.org/testdivision/items/J8QG2849",
            "type": "text/html",
        },
        "self": {
            "href": "https://api.zotero.org/users/9467580/items/J8QG2849",
            "type": "application/json",
        },
    },
    "meta": {
        "creatorSummary": "Sellbom and Michael",
        "numChildren": 0,
        "parsedDate": "2010",
    },
    "version": 1818,
}
