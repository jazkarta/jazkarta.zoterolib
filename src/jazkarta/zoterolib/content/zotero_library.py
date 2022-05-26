# -*- coding: utf-8 -*-
import Acquisition
from plone import api
from plone.dexterity.content import Item
from plone.supermodel import model
from plone.uuid.interfaces import IUUID, IAttributeUUID
from pyzotero import zotero
from zope import schema
from zope.event import notify
from zope.interface import Interface
from zope.interface import implementer
from zope.lifecycleevent import ObjectCreatedEvent

from jazkarta.zoterolib import _


class IZoteroLibrary(model.Schema):
    """Marker interface and Dexterity Python Schema for ZoteroLibrary"""

    zotero_library_id = schema.Int(
        title=_("Zotero Library Id"),
        description=_("The ID of the Zotero library"),
        required=True,
    )

    zotero_library_type = schema.Choice(
        title=_("Zotero Library Type"),
        description=_("The type of Zotero Library"),
        required=True,
        default="group",
        values=("group", "user"),
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

        current_batch = zotero_api.top(start=start, limit=limit)
        while current_batch:
            for item in current_batch:
                yield item
            if "next" in zotero_api.links:
                current_batch = zotero_api.follow()
            else:
                current_batch = []

    def fetch_and_index_items(self):
        # for item in self.fetch_items(start=start, limit=limit):
        #     pass
        pass


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
        return self.zotero_item["key"]

    def Authors(self):
        return ", ".join(self.AuthorItems())

    def AuthorItems(self):
        return [
            el.get("firstName", "") + " " + el.get("lastName", "")
            for el in self.zotero_item["data"]["creators"]
            if el["creatorType"] == "author"
        ]

    def Title(self):
        return self.zotero_item["data"]["title"]

    def Description(self):
        res = []
        if self.zotero_item["data"].get("publicationTitle"):
            res.append(self.zotero_item["data"]["publicationTitle"])
        if self.zotero_item["data"].get("title"):
            res.append(self.zotero_item["data"]["title"])
        return " - ".join(res)

    def SearchableText(self):
        """Concatenate text information into a single searchable field"""
        return " ".join([self.Title(), self.Authors()])

    def allowedRolesAndUsers(self):
        # XXX: should we try to get this value from the "container"?
        return ["Anonymous", "Authenticated"]

    def getPath(self):
        return self.path

    def getPhysicalPath(self):
        return tuple(self.path.split("/"))

    def UID(self):
        return IUUID(self)
