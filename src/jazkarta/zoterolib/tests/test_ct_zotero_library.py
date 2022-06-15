# -*- coding: utf-8 -*-
from itertools import islice
from jazkarta.zoterolib.testing import JAZKARTA_ZOTEROLIB_FUNCTIONAL_TESTING
from jazkarta.zoterolib.content.zotero_library import IZoteroLibrary
from jazkarta.zoterolib.testing import JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING
from jazkarta.zoterolib.testing import JAZKARTA_ZOTEROLIB_FUNCTIONAL_TESTING
from jazkarta.zoterolib.utils import plone_encode
from plone import api
from plone.app.testing import setRoles, TEST_USER_ID
from plone.dexterity.interfaces import IDexterityFTI

try:
    from plone.testing.zope import Browser
except ImportError:
    from plone.testing.z2 import Browser
from zope.component import createObject, queryUtility
import requests_mock
import os
from .mock_data import fill_mocker
import unittest


REAL_HTTP = bool(os.environ.get("REAL_HTTP"))


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
        self.assertEqual(
            item.Authors(),
            plone_encode(u"Rainer Simon, Elton Barker, Leif Isaksen, Soto Cañamares"),
        )
        self.assertEqual(item.AuthorItems(), item.Authors().split(", "))
        self.assertEqual(item.Subject(), [plone_encode(u"\u26d4 No DOI found")])
        self.assertEqual(item.Type, "Journal Article Reference")
        self.assertEqual(item.portal_type, "ExternalZoteroItem")
        self.assertEqual(item.contentType, "Zotero Reference")
        self.assertEqual(
            item.getRemoteUrl(),
            "https://www.zotero.org/groups/isaw_papers/items/6DAWH9QK",
        )
        self.assertEqual(item.publication_year, 2015)


class ZoteroLibraryIndexTest(unittest.TestCase):

    layer = JAZKARTA_ZOTEROLIB_FUNCTIONAL_TESTING

    def setUp(self):
        """Create a Zotero Library object."""
        self.portal = self.layer["portal"]
        self.catalog = self.portal.portal_catalog
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.parent = self.portal
        self.obj = api.content.create(
            container=self.portal,
            type="Zotero Library",
            id="zotero_library",
            zotero_library_id=242005,
            zotero_library_type="group",
            citation_style="modern-language-association",
        )
        api.content.transition(obj=self.obj, transition="publish")

    def test_index_external_item(self):
        with requests_mock.Mocker() as m:
            fill_mocker(m)
            self.obj.index_element(TEST_ENTRY)
        results = self.catalog.searchResults(getAuthors="Isaksen")
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0].Authors,
            plone_encode(u"Rainer Simon, Elton Barker, Leif Isaksen, Soto Cañamares"),
        )
        self.assertEqual(results[0].portal_type, "ExternalZoteroItem")

    def test_fetch_external_items(self):
        with requests_mock.Mocker() as m:
            fill_mocker(m)
            result_iterator = self.obj.fetch_items()
            result = tuple(result_iterator)
            self.assertTrue(len(result) > 150)

    def test_fetch_and_index_external_items(self):
        with requests_mock.Mocker() as m:
            fill_mocker(m)
            self.obj.fetch_and_index_items()
        results = self.catalog.searchResults(
            getAuthors=plone_encode(u"Cañamares"), sort_on="effective"
        )
        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(
            results[0].Title,
            plone_encode(
                u"Linking Early Geospatial Documents, One Place at a Time: Annotation of Geographic Documents with Recogito"
            ),
        )

    def test_update_items(self):
        with requests_mock.Mocker(real_http=REAL_HTTP) as m:
            fill_mocker(m)
            self.obj.fetch_and_index_items()
        self.assertEqual(
            len(self.catalog.searchResults(portal_type="ExternalZoteroItem")), 180
        )
        # Simulate new items on Zotero by removing the ones with most recent modification time
        to_delete = self.catalog.searchResults(
            sort_on='modified', portal_type="ExternalZoteroItem"
        )[-10:]
        for brain in to_delete:
            self.catalog.uncatalog_object(brain.getPath())
        self.assertEqual(
            len(self.catalog.searchResults(portal_type="ExternalZoteroItem")), 170
        )
        with requests_mock.Mocker(real_http=REAL_HTTP) as m:
            fill_mocker(m)
            self.obj.update_items()
        results = self.catalog.searchResults(portal_type="ExternalZoteroItem")
        self.assertEqual(len(results), 180)

    def validate_example_item(self, item):
        self.assertEqual(item.portal_type, "ExternalZoteroItem")
        self.assertEqual(item.Type, "Journal Article Reference")
        self.assertEqual(item.getId(), plone_encode(TEST_ENTRY["key"]))
        self.assertEqual(item.Title(), plone_encode(TEST_ENTRY["data"]["title"]))
        self.assertEqual(
            item.getRemoteUrl(), plone_encode(TEST_ENTRY["links"]["alternate"]["href"])
        )
        self.assertEqual(
            item.Description(),
            plone_encode(
                u"Simon, Rainer, et al. “Linking Early Geospatial Documents, One Place at a Time: Annotation of Geographic Documents with Recogito.” E-Perimetron, vol. 10, no. 2, 2015, pp. 49–59."
            ),
        )
        self.assertEqual(item.text, plone_encode(TEST_ENTRY["bib"]))

    def test_external_item_get_object(self):
        self.obj.index_element(TEST_ENTRY)
        catalog = api.portal.get_tool("portal_catalog")
        results = catalog.searchResults(getAuthors="Barker")
        item = results[0].getObject()
        self.validate_example_item(item)

    def test_traverse_to_external_item(self):
        self.obj.index_element(TEST_ENTRY)
        item = self.obj.unrestrictedTraverse("zotero_items/6DAWH9QK")
        self.validate_example_item(item)

    def test_view_external_item(self):
        self.obj.index_element(TEST_ENTRY)
        brain = self.catalog.searchResults(getAuthors=plone_encode(u"Cañamares"))[0]
        # need a commit to make the content visible to test browser
        import transaction

        transaction.commit()
        browser = Browser(self.layer["app"])
        browser.handleErrors = False
        browser.open(brain.getURL())
        self.assertIn('<div class="csl-bib-body"', browser.contents)


TEST_ENTRY = {
    "key": u"6DAWH9QK",
    "version": 531,
    "library": {
        "type": u"group",
        "id": 242005,
        "name": u"ISAW Papers",
        "links": {
            "alternate": {
                "href": u"https://www.zotero.org/groups/isaw_papers",
                "type": u"text/html",
            }
        },
    },
    "links": {
        "self": {
            "href": u"https://api.zotero.org/groups/242005/items/6DAWH9QK",
            "type": u"application/json",
        },
        "alternate": {
            "href": u"https://www.zotero.org/groups/isaw_papers/items/6DAWH9QK",
            "type": u"text/html",
        },
    },
    "meta": {
        "createdByUser": {
            "id": 50458,
            "username": u"sebastianheath",
            "name": u"Sebastian Heath",
            "links": {
                "alternate": {
                    "href": u"https://www.zotero.org/sebastianheath",
                    "type": u"text/html",
                }
            },
        },
        "lastModifiedByUser": {
            "id": 465,
            "username": u"paregorios",
            "name": u"Tom Elliott",
            "links": {
                "alternate": {
                    "href": u"https://www.zotero.org/paregorios",
                    "type": u"text/html",
                }
            },
        },
        "creatorSummary": u"Simon et al.",
        "parsedDate": u"2015",
        "numChildren": 0,
    },
    "bib": u'<div class="csl-bib-body" style="line-height: 2; padding-left: 1em; text-indent:-1em;">\n  <div class="csl-entry">Simon, Rainer, et al. &#x201C;Linking Early Geospatial Documents, One Place at a Time: Annotation of Geographic Documents with Recogito.&#x201D; <i>E-Perimetron</i>, vol. 10, no. 2, 2015, pp. 49&#x2013;59.</div>\n</div>',
    "citation": u"<span>(Simon et al.)</span>",
    "data": {
        "key": u"6DAWH9QK",
        "version": 531,
        "itemType": u"journalArticle",
        "title": u"Linking Early Geospatial Documents, One Place at a Time: Annotation of Geographic Documents with Recogito",
        "creators": [
            {"creatorType": u"author", "firstName": u"Rainer", "lastName": u"Simon"},
            {"creatorType": "author", "firstName": u"Elton", "lastName": u"Barker"},
            {"creatorType": "author", "firstName": u"Leif", "lastName": u"Isaksen"},
            {
                "creatorType": u"author",
                "firstName": u"Soto",
                "lastName": u"Ca\u00f1amares",
            },
        ],
        "abstractNote": u"",
        "publicationTitle": u"e-Perimetron",
        "volume": u"10",
        "issue": u"2",
        "pages": u"49-59",
        "date": u"2015",
        "series": u"",
        "seriesTitle": u"",
        "seriesText": u"",
        "journalAbbreviation": u"",
        "language": u"",
        "DOI": u"",
        "ISSN": u"1790-3769",
        "shortTitle": u"",
        "url": u"",
        "accessDate": u"",
        "archive": u"",
        "archiveLocation": u"",
        "libraryCatalog": u"",
        "callNumber": u"",
        "rights": u"",
        "extra": u"",
        "tags": [{"tag": u"\u26d4 No DOI found", "type": 1}],
        "collections": [u"DZDZS5QD"],
        "relations": {
            "dc:relation": [
                u"http://zotero.org/groups/242005/items/T79TMG8G",
                u"http://zotero.org/groups/242005/items/9USWD24D",
            ]
        },
        "dateAdded": u"2021-05-03T14:03:48Z",
        "dateModified": u"2021-12-11T11:50:07Z",
    },
}
