# -*- coding: utf-8 -*-
import Acquisition
import Missing
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

    zotero_library_id = schema.TextLine(
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


class IExternalZoteroItem(Interface):
    """identity interface for external page fake brains"""


@implementer(IExternalZoteroItem, IAttributeUUID)
class ExternalZoteroItem(Acquisition.Implicit):
    portal_type = meta_type = "ExternalZoteroItem"
    contentType = Type = "Zotero Reference"
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
                self.zotero_item["id"],
            )
        )

    def getId(self):
        return self.zotero_item["id"]

    def Authors(self):
        return ", ".join(self.zotero_item["authors"])

    def AuthorItems(self):
        return self.zotero_item["authors"]

    def Title(self):
        return self.zotero_item["title"]

    def Description(self):
        return self.zotero_item["citationLabel"]

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


class BrainProxy(Acquisition.Implicit):

    callables = frozenset(
        (
            "getId",
            "Title",
            "Description",
            "UID",
            "Authors",
            "AuthorItems",
        )
    )

    def __init__(self, brain, parent=None):
        self.brain = brain
        if parent:
            self.__parent__ = parent

    @property
    def __name__(self):
        return self.brain.getId

    def __getattr__(self, name):
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
