# -*- coding: utf-8 -*-
import unittest
import six
from jazkarta.zoterolib import utils
from jazkarta.zoterolib.testing import JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING


class ZoteroLibraryUtilsTest(unittest.TestCase):
    def test_plone_encode(self):
        test_str = u"Ca\u00f1amares"
        if six.PY3:
            self.assertIs(utils.plone_encode(test_str), test_str)
        else:
            self.assertEqual(utils.plone_encode(test_str), test_str.encode('utf8'))

    def test_camel_case_splitter(self):
        self.assertEqual(utils.camel_case_splitter('journalArticle'), 'Journal Article')
        self.assertEqual(
            utils.camel_case_splitter('AFunnyThingHappenedYesterday'),
            'A Funny Thing Happened Yesterday',
        )
        self.assertEqual(utils.camel_case_splitter('Two20AndSix'), 'Two20 And Six')


class ZoteroLibraryUtilsIntegrationTest(unittest.TestCase):

    layer = JAZKARTA_ZOTEROLIB_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer["portal"]
        self.parent = self.portal

    def test_html_to_plain_text(self):
        self.assertEqual(
            utils.html_to_plain_text('\r\n<div>Some Stuff</div>\n\n'), 'Some Stuff'
        )
        self.assertEqual(
            utils.html_to_plain_text(
                '\r\n<random>Some <spam>Stuff</spam> <br /></random>\n\n'
            ),
            'Some  Stuff',
        )
        self.assertEqual(
            utils.html_to_plain_text(
                '\r\n<broken>Some <spam>Stuff</span> <dr /></really_broken>\n\n'
            ),
            'Some  Stuff',
        )
