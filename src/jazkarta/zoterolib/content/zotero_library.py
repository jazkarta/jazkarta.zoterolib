# -*- coding: utf-8 -*-
import Acquisition
import dateutil
import gzip
import json
import os
import pytz
import six
import uuid
from DateTime import DateTime
from plone import api
from plone.dexterity.content import Item
from plone.supermodel import model
from plone.uuid.interfaces import IUUID, IAttributeUUID, IMutableUUID
from Products.CMFPlone.utils import safe_encode
from pyzotero import zotero
from zope import schema
from zope.event import notify
from zope.interface import Interface
from zope.interface import implementer
from zope.lifecycleevent import ObjectCreatedEvent
from zope.schema.vocabulary import SimpleVocabulary
from zope.schema.vocabulary import SimpleTerm

from jazkarta.zoterolib import _


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

    def index_element(self, element):
        obj = ExternalZoteroItem(parent=self, zotero_item=element).__of__(self)
        notify(ObjectCreatedEvent(obj))
        catalog = api.portal.get_tool("portal_catalog")
        catalog.catalog_object(obj, uid=obj.path)

    def fetch_items(self, start=0, limit=100):
        """Iterates over ALL remote items, starting at the given offset.
        The limit will be used to determine how many items to retrieve at once.
        """
        zotero_api = zotero.Zotero(self.zotero_id, self.zotero_library_type)

        current_batch = zotero_api.items(
            start=start,
            limit=limit,
            include="data,bib,citation",
            style=self.citation_style,
        )
        while current_batch:
            for item in current_batch:
                yield item
            if "next" in zotero_api.links:
                current_batch = zotero_api.follow()
            else:
                current_batch = []

    def fetch_and_index_items(self):
        for item in self.fetch_items():
            self.index_element(item)


class IExternalZoteroItem(Interface):
    """identity interface for external page fake brains"""


@implementer(IExternalZoteroItem, IAttributeUUID)
class ExternalZoteroItem(Acquisition.Implicit):
    portal_type = meta_type = "ExternalZoteroItem"
    contentType = Type = "ExternalItem"
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

    def allowedRolesAndUsers(self):
        # XXX: should we try to get this value from the "container"?
        return ["Anonymous", "Authenticated"]

    def getPath(self):
        return self.path

    def getPhysicalPath(self):
        return tuple(self.path.split("/"))

    def UID(self):
        return IUUID(self)
