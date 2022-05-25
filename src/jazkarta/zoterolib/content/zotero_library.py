# -*- coding: utf-8 -*-
import Acquisition
from plone import api
from plone.dexterity.content import Item
from plone.supermodel import model
from plone.uuid.interfaces import IUUID, IAttributeUUID
from zope import schema
from zope.event import notify
from zope.interface import Interface
from zope.interface import implementer
from zope.lifecycleevent import ObjectCreatedEvent


from jazkarta.zoterolib import _


class IZoteroLibrary(model.Schema):
    """Marker interface and Dexterity Python Schema for ZoteroLibrary"""

    zotero_url = schema.TextLine(
        title=_("Zotero URL"),
        description=_("The URL of the Zotero library"),
        required=True,
    )


@implementer(IZoteroLibrary)
class ZoteroLibrary(Item):
    """Content-type class for IZoteroLibrary"""

    def index_element(self, element):
        obj = ExternalZoteroItem(element).__of__(self)
        notify(ObjectCreatedEvent(obj))
        catalog = api.portal.get_tool("portal_catalog")
        catalog.catalog_object(obj, uid=obj.path)


class IExternalZoteroItem(Interface):
    """identity interface for external page fake brains"""


@implementer(IExternalZoteroItem, IAttributeUUID)
class ExternalZoteroItem(Acquisition.Implicit):
    portal_type = meta_type = "ExternalZoteroItem"
    contentType = Type = "ExternalItem"
    review_state = "published"

    def __init__(self, zotero_item):
        self.zotero_item = zotero_item
        self.path = "/TODO/set/a/path/for/this/item"

    def getId(self):
        return self.zotero_item["id"]

    def Authors(self):
        return ", ".join(self.zotero_item["authors"])

    def AuthorItems(self):
        return self.zotero_item["authors"]

    def Title(self):
        return self.zotero_item["title"]

    Description = Title

    def SearchableText(self):
        """Concatenate text information into a single searchable field"""
        return " ".join([self.Title(), self.Authors()])

    def allowedRolesAndUsers(self):
        return ["Anonymous", "Authenticated"]

    def getPath(self):
        return self.path

    def getPhysicalPath(self):
        return tuple(self.path.split("/"))

    def UID(self):
        return IUUID(self)
