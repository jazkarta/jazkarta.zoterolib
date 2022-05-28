# -*- coding: utf-8 -*-
import Acquisition
import dateutil
import gzip
import json
import logging
import Missing
import os
import pytz
import six
import uuid
from AccessControl.SecurityInfo import ClassSecurityInfo
from DateTime import DateTime
from plone import api
from plone.dexterity.content import Item
from plone.supermodel import model
from plone.app.contentlisting.interfaces import IContentListing
from plone.batching import Batch
from plone.uuid.interfaces import IUUID, IAttributeUUID, IMutableUUID
from Products.CMFCore import permissions
from Products.CMFPlone.utils import safe_encode, safe_unicode
from pyzotero import zotero
from zope import schema
from zope.event import notify
from zope.interface import Interface
from zope.interface import implementer
from zope.lifecycleevent import ObjectCreatedEvent
from zope.schema.vocabulary import SimpleVocabulary
from zope.schema.vocabulary import SimpleTerm

from jazkarta.zoterolib import _
from jazkarta.zoterolib.utils import camel_case_splitter
from jazkarta.zoterolib.utils import html_to_plain_text


logger = logging.getLogger(__name__)

with gzip.open(
    os.path.join(os.path.dirname(__file__), "../browser/static/styles.json.gz")
) as styles_file:
    styles_data = json.load(styles_file)

styles_vocab = SimpleVocabulary(
    [
        SimpleTerm(title=i["title"], value=i["name"], token=str(i["name"]))
        for i in styles_data
    ]
)


class IZoteroLibrary(model.Schema):
    """Marker interface and Dexterity Python Schema for ZoteroLibrary"""

    zotero_library_id = schema.Int(
        title=_(u"Zotero Library Id"),
        description=_(u"The ID of the Zotero library"),
        required=True,
    )

    zotero_library_type = schema.Choice(
        title=_(u"Zotero Library Type"),
        description=_(u"The type of Zotero Library"),
        required=True,
        default=u"group",
        values=(u"group", u"user"),
    )

    citation_style = schema.Choice(
        title=_(u"Citation Style Format"),
        required=True,
        default=u"modern-language-association",
        vocabulary=styles_vocab,
    )


@implementer(IZoteroLibrary)
class ZoteroLibrary(Item):
    """Content-type class for IZoteroLibrary"""

    security = ClassSecurityInfo()

    def index_element(self, element):
        obj = ExternalZoteroItem(parent=self, zotero_item=element).__of__(self)
        notify(ObjectCreatedEvent(obj))
        catalog = api.portal.get_tool("portal_catalog")
        catalog.catalog_object(obj, uid=obj.path)

    def fetch_items(self, start=0, limit=100):
        """Iterates over ALL remote items, starting at the given offset.
        The limit will be used to determine how many items to retrieve at once.
        """
        zotero_api = zotero.Zotero(self.zotero_library_id, self.zotero_library_type)

        current_batch = zotero_api.items(
            start=start,
            limit=limit,
            include="data,bib,citation",
            style=self.citation_style,
        )
        page = 1
        while current_batch:
            logger.log(
                logging.INFO,
                'Fetched page {} for Zotero Library {}'.format(
                    page, self.zotero_library_id
                ),
            )
            for item in current_batch:
                yield item
            if "next" in zotero_api.links:
                current_batch = zotero_api.follow()
                page += 1
            else:
                current_batch = []

    def fetch_and_index_items(self, start=0, limit=100):
        count = 0
        for item in self.fetch_items(start, limit):
            self.index_element(item)
            count += 1
        return count

    def clear_items(self):
        contents = self.results(batch=False, brains=True)
        logger.log(
            logging.INFO,
            'Removing all {} items indexed for Zotero Library {}'.format(
                len(contents), self.zotero_library_id
            ),
        )
        catalog = api.portal.get_tool('portal_catalog')
        for brain in contents:
            catalog.uncatalog_object(brain.getPath())

    @security.protected(permissions.View)
    def queryCatalog(self, batch=True, b_start=0, b_size=30, sort_on=None):
        return self.results(batch, b_start, b_size, sort_on=sort_on)

    @security.protected(permissions.View)
    def results(
        self,
        batch=True,
        b_start=0,
        b_size=None,
        sort_on=None,
        limit=None,
        brains=False,
        custom_query=None,
    ):
        query = {
            'portal_type': 'ExternalZoteroItem',
            'path': {'query': '/'.join(self.getPhysicalPath()), 'depth': -1},
            'sort_on': sort_on or 'sortable_title',
        }
        if limit:
            query['sort_limit'] = limit
        if custom_query:
            # The @@folderListing view for collections filters by type, ignore it.
            if 'portal_type' in custom_query:
                del custom_query['portal_type']
                # We should never batch from @@folderListing, because we'll get
                # double batched
                batch = False
            query.update(custom_query)
        catalog = api.portal.get_tool('portal_catalog')
        results = catalog(**query)
        if not brains:
            results = IContentListing(results)
        if batch:
            results = Batch(results, b_size, start=b_start)
        return results


class IExternalZoteroItem(Interface):
    """identity interface for external page fake brains"""


@implementer(IExternalZoteroItem, IAttributeUUID)
class ExternalZoteroItem(Acquisition.Implicit):
    portal_type = meta_type = "ExternalZoteroItem"
    contentType = "Zotero Reference"
    review_state = "published"

    def __init__(self, parent, zotero_item):
        """For some reason `self` might not be acquisition-wrapped in some cases.
        I observed `self` correctly wrapped while in `getPhysicalPath`, and
        not wrapped anymore when we get in the `path` method.
        For this reason we require an explicit `parent` argument, instead of
        relying on acquisition.
        """
        self.parent = parent
        self.zotero_item = zotero_item
        uid = str(uuid.uuid5(uuid.NAMESPACE_URL, zotero_item["links"]["self"]["href"]))
        IMutableUUID(self).set(uid)

    def _plone_encode(self, val):
        """In Plone on Python 2, some catalog indexes expect encoded values"""
        if six.PY3:
            return val
        return safe_encode(val)

    @property
    def Type(self):
        ref_type = self.zotero_item["data"]["itemType"]
        type_name = camel_case_splitter(ref_type)
        return self._plone_encode(type_name) + " Reference"

    @property
    def path(self):
        return "/".join(
            self.parent.getPhysicalPath()
            + (
                "zotero_items",
                self.zotero_item["key"],
            )
        )

    def getId(self):
        return self._plone_encode(self.zotero_item["key"])

    def Authors(self):
        return ", ".join(self._plone_encode(v) for v in self.AuthorItems())

    def AuthorItems(self):
        return [
            self._plone_encode(el.get("firstName", ""))
            + " "
            + self._plone_encode(el.get("lastName", ""))
            for el in self.zotero_item["data"].get("creators", [])
            if el["creatorType"] == "author"
        ]

    def Title(self):
        return self._plone_encode(self.zotero_item["data"]["title"])

    def sortable_title(self):
        return self.Title().lower()

    def Description(self):
        return self._plone_encode(self.zotero_item["bib"])

    def Subject(self):
        return [
            self._plone_encode(t["tag"])
            for t in self.zotero_item["data"].get("tags", [])
        ]

    def SearchableText(self):
        """Concatenate text information into a single searchable field"""
        return " ".join([self.Title(), self.Authors(), self.Description()]) + " ".join(
            self.Subject()
        )

    def CreationDate(self):
        return self.zotero_item["data"].get("dateAdded")

    def created(self):
        date = self.CreationDate()
        if date is not None:
            return DateTime(date)

    def ModificationDate(self):
        return self.zotero_item["data"].get("dateAdded")

    def modified(self):
        date = self.ModificationDate()
        if date is not None:
            return DateTime(date)

    def effective(self):
        date = self.zotero_item["meta"].get("parsedDate")
        if date is not None:
            return pytz.utc.localize(dateutil.parser.parse(date))

    def EffectiveDate(self):
        date = self.effective()
        if date is not None:
            return date.isoformat()

    @property
    def publication_year(self):
        date = self.effective()
        if date is None:
            try:
                return int(self.zotero_item["data"].get("date"))
            except (ValueError, TypeError):
                return
        return date.year

    def Date(self):
        return self.EffectiveDate() or self.CreationDate()

    def allowedRolesAndUsers(self):
        # XXX: should we try to get this value from the "container"?
        return ["Anonymous", "Authenticated"]

    def getPath(self):
        return self.path

    def getPhysicalPath(self):
        return tuple(self.path.split("/"))

    def getRemoteUrl(self):
        return self.zotero_item["links"]["alternate"]["href"]

    def UID(self):
        return IUUID(self)


class BrainProxy(Acquisition.Implicit):

    callables = frozenset(
        (
            "getId",
            "Title",
            "UID",
            "Authors",
            "AuthorItems",
            "Subject",
            "created",
            "effective",
            "expires",
            "CreationDate",
            "ModificationDate",
            "EffectiveDate",
            "Date",
            "getRemoteUrl",
        )
    )

    def __init__(self, brain, parent=None):
        self.brain = brain
        if parent:
            self.__parent__ = parent
        # We stored HTML for Description, but we want `Description()` to return
        # plain text
        self.text = safe_unicode(self.brain.Description)

    @property
    def __name__(self):
        return self.brain.getId

    def Description(self):
        value = html_to_plain_text(self.text)
        if not six.PY3:
            value = safe_encode(value)
        return value.strip()

    def __getattr__(self, name):
        if name in ('getObject', 'getPath', 'getURL'):
            # We are not a brain
            raise AttributeError
        # Get it from the brain
        value = getattr(Acquisition.aq_base(self.brain), name, Missing.Value)
        if value is Missing.Value:
            # If it's not on the brain, get it via acquisition
            return super(BrainProxy, self).__getattr__(name)
        # If it's a name that should be a callable, make it so
        if name in self.callables:
            return lambda: value
        return value

    def getPhysicalPath(self):
        return self.brain.getPath().split("/")
