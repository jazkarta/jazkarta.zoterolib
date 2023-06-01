# -*- coding: utf-8 -*-
import Acquisition
from Products.CMFCore.utils import getToolByName
import dateutil
import logging
import Missing
import pytz
import six
import uuid
from AccessControl.SecurityInfo import ClassSecurityInfo
from collections import namedtuple
from DateTime import DateTime
from OFS.SimpleItem import SimpleItem
from OFS.Traversable import Traversable
from plone.dexterity.content import Item
from plone.supermodel import model
from plone.app.contentlisting.interfaces import IContentListing
from plone.autoform import directives as form
from plone.batching import Batch
from plone.uuid.interfaces import IUUID, IAttributeUUID, IMutableUUID
from plone.app.z3cform.widget import AjaxSelectWidget
from Products.CMFCore import permissions
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import safe_unicode
from pyzotero import zotero
from zExceptions import NotFound
from zope import schema
from zope.component import adapter
from zope.event import notify
from zope.interface import Interface
from zope.interface import implementer
from zope.lifecycleevent import ObjectCreatedEvent
from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectMovedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from jazkarta.zoterolib import _
from jazkarta.zoterolib.utils import camel_case_splitter
from jazkarta.zoterolib.utils import html_to_plain_text
from jazkarta.zoterolib.utils import plone_encode


logger = logging.getLogger(__name__)
INDEXED_ZOTERO_CREATOR_TYPES = set()


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
        description=_(
            u'If you change this value on a populated Zotero '
            u'Library you will need to use "Clear and Update Library" '
            u'from the "Update Zotero Library" action on the '
            u'Actions menu to bring in the new style.'
        ),
        required=True,
        default=u"modern-language-association",
        vocabulary=u'jazkarta.zoterolib.citations-styles',
    )
    form.widget(
        'citation_style',
        AjaxSelectWidget,
        pattern_options={
            "minimumInputLength": 5,
            "ajax": {"delay": 500},
        },
    )


@implementer(IZoteroLibrary)
class ZoteroLibrary(Item):
    """Content-type class for IZoteroLibrary"""

    security = ClassSecurityInfo()
    _last_modified = 0

    def index_element(self, element):
        obj = ExternalZoteroItem(parent=self, zotero_item=element).__of__(self)
        notify(ObjectCreatedEvent(obj))
        catalog = getToolByName(self, "portal_catalog")
        catalog.catalog_object(obj, uid=obj.path)

    def fetch_items(self, start=0, limit=100, since=0):
        """Iterates over ALL remote items, starting at the given offset.
        The limit will be used to determine how many items to retrieve at once.
        """
        zotero_api = zotero.Zotero(self.zotero_library_id, self.zotero_library_type)

        current_batch = zotero_api.items(
            start=start,
            limit=limit,
            include="data,bib,citation",
            style=self.citation_style,
            sort="dateModified",
            direction="asc",
            since=since,
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

    @property
    def last_modified_version(self):
        return self._last_modified

    def update_modified_version(self, version=None):
        if version is None:
            zotero_api = zotero.Zotero(self.zotero_library_id, self.zotero_library_type)
            version = zotero_api.last_modified_version()
        self._last_modified = version
        return self._last_modified

    def update_items(self, start=0, limit=100):
        last_modified = self.last_modified_version
        removed = self.remove_recently_deleted()
        updated = self.fetch_and_index_items(start, limit, last_modified)
        return {'removed': removed, 'updated': updated}

    def fetch_and_index_items(self, start=0, limit=100, since=0):
        """Fetch ALL zotero items in batches of `limit` items, since the
        specified version, and index them in the catalog.
        """
        count = 0
        for item in self.fetch_items(start, limit, since):
            self.index_element(item)
            count += 1

        self.update_modified_version()
        return count

    def remove_recently_deleted(self, since=None):
        if since is None:
            since = self.last_modified_version
        zotero_api = zotero.Zotero(self.zotero_library_id, self.zotero_library_type)
        trash = [i['key'] for i in zotero_api.trash()]
        deleted = zotero_api.deleted(since=since)['items']
        catalog = getToolByName(self, "portal_catalog")
        count = 0
        for key in trash + deleted:
            try:
                catalog.uncatalog_object(
                    '/'.join(self.getPhysicalPath())
                    + '/zotero_items/'
                    + plone_encode(key)
                )
                count += 1
            except KeyError:
                logger.log(
                    logging.INFO, 'Error removing deleted Zotero Item {}'.format(key)
                )
        return count

    def clear_items(self):
        contents = self.results(batch=False, brains=True)
        logger.log(
            logging.INFO,
            'Removing all {} items indexed for Zotero Library {}'.format(
                len(contents), self.zotero_library_id
            ),
        )
        catalog = getToolByName(self, "portal_catalog")
        for brain in contents:
            catalog.uncatalog_object(brain.getPath())

    def query(self):
        return {
            'portal_type': 'ExternalZoteroItem',
            'path': {'query': '/'.join(self.getPhysicalPath()), 'depth': -1},
        }

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
        query = self.query()
        query['sort_on'] = sort_on or 'sortable_title'
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
        catalog = getToolByName(self, "portal_catalog")
        results = catalog(**query)
        if not brains:
            results = IContentListing(results)
        if batch:
            results = Batch(results, b_size, start=b_start)
        return results


@adapter(IZoteroLibrary, IObjectRemovedEvent)
def removeLibraryItemsOnDelete(library, event):
    logger.log(
        logging.INFO,
        u'Removing all library contents before deleting library at: {}'.format(
            library.absolute_url(1)
        ),
    )
    library.clear_items()


@adapter(IZoteroLibrary, IObjectMovedEvent)
def reindexLibraryItemsOnMove(library, event):
    # Some "move" events are actually deletions or adds
    if IObjectRemovedEvent.providedBy(event) or IObjectAddedEvent.providedBy(event):
        return
    catalog = getToolByName(library, "portal_catalog")
    _catalog = catalog._catalog
    path_index = _catalog.getIndex('path')
    old_path = '/'.join(event.oldParent.getPhysicalPath() + (event.oldName,))
    brains = catalog.unrestrictedSearchResults(
        portal_type='ExternalZoteroItem', path={'query': old_path, 'depth': -1}
    )
    logger.log(
        logging.INFO,
        u'Moving {} indexed library contents for library at: {}'.format(
            len(brains), library.absolute_url(1)
        ),
    )
    path_tuple = namedtuple('path_obj', ['path'])
    for b in brains:
        # Use catalog internals to manually move catalog data
        # Catalog metadata should remain unchanged
        old_path = b.getPath()
        new_path = '/'.join(library.getPhysicalPath() + ("zotero_items", b.getId))
        rid = _catalog.uids[old_path]
        del _catalog.uids[old_path]
        _catalog.uids[new_path] = rid
        del _catalog.paths[rid]
        _catalog.paths[rid] = new_path
        # Update path index
        path_obj = path_tuple(new_path)
        path_index.unindex_object(rid)
        path_index.index_object(rid, path_obj)


class IExternalZoteroItem(Interface):
    """identity interface for external page fake brains"""


@implementer(IExternalZoteroItem, IAttributeUUID)
class ExternalZoteroItem(SimpleItem):
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
        item_href = zotero_item["links"]["self"]["href"]
        item_href = plone_encode(item_href)
        uid = str(uuid.uuid5(uuid.NAMESPACE_URL, item_href))
        IMutableUUID(self).set(uid)

    def __getattr__(self, name):
        # No implicit acquisition during indexing
        return None

    @property
    def Type(self):
        ref_type = self.zotero_item["data"].get("itemType") or "Bibliographic"
        type_name = camel_case_splitter(ref_type)
        return plone_encode(type_name) + " Reference"

    @property
    def path(self):
        return "/".join(
            self.parent.getPhysicalPath()
            + (
                "zotero_items",
                plone_encode(self.zotero_item["key"]),
            )
        )

    def getId(self):
        return plone_encode(self.zotero_item["key"])

    def Authors(self):
        return ", ".join(plone_encode(v) for v in self.AuthorItems())

    getAuthors = Authors

    def AuthorItems(self):
        return [
            plone_encode(el.get("firstName", ""))
            + " "
            + plone_encode(el.get("lastName", ""))
            for el in self.zotero_item["data"].get("creators", [])
            if not INDEXED_ZOTERO_CREATOR_TYPES
            or el["creatorType"] in INDEXED_ZOTERO_CREATOR_TYPES
        ]

    def Title(self):
        return plone_encode(
            self.zotero_item["data"].get("title")
            or self.zotero_item["data"].get("shortTitle")
            or self.zotero_item.get("citation")
            or ""
        )

    def citationLabel(self):
        return plone_encode(self.zotero_item.get("citation") or "")

    def Source(self):
        return plone_encode(self.zotero_item.get("publicationTitle") or "")

    def sortable_title(self):
        return self.Title().lower()

    def Description(self):
        return plone_encode(self.zotero_item.get("bib") or "")

    def Subject(self):
        return [
            plone_encode(t["tag"]) for t in self.zotero_item["data"].get("tags", [])
        ]

    bib_tags = Subject

    def SearchableText(self):
        """Concatenate text information into a single searchable field"""
        return " ".join([self.Title(), self.Authors(), self.Description()]) + " ".join(
            self.Subject()
        )

    def CreationDate(self):
        return self.zotero_item["data"].get("dateAdded") or DateTime().HTML4()

    def created(self):
        date = self.CreationDate()
        if date is not None:
            return DateTime(date)

    def ModificationDate(self):
        return self.zotero_item["data"].get("dateModified") or self.CreationDate()

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
        return plone_encode(self.zotero_item["links"]["alternate"]["href"])

    def UID(self):
        return IUUID(self)


class BrainProxy(Traversable, Acquisition.Implicit):

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
        plone_encode(value)
        return value.strip()

    def __getattr__(self, name):
        if name in ('getObject', 'getPath', 'getURL'):
            # We are not a brain
            raise AttributeError(name)
        # Get it from the brain
        value = getattr(Acquisition.aq_base(self.brain), name, Missing.Value)
        if value is Missing.Value:
            # If it's not on the brain, get it via acquisition
            return super(BrainProxy, self).__getattr__(name)
        # If it's a name that should be a callable, make it so
        if name in self.callables:
            return lambda: value
        return value

    @property
    def title(self):
        return safe_unicode(self.Title())

    @property
    def path(self):
        return "/".join(
            self.__parent__.getPhysicalPath() + ("zotero_items", self.getId())
        )

    def getPhysicalPath(self):
        return tuple(self.path.split("/"))

    def created(self):
        date = self.CreationDate()
        if date is not None:
            return DateTime(date)

    def modified(self):
        date = self.ModificationDate()
        if date is not None:
            return DateTime(date)

    def effective(self):
        date = self.EffectiveDate()
        if date is not None:
            return DateTime(date)

    def expires(self):
        return None

    def ExpirationDate(self):
        return None

    def AuthorItems(self):
        authors = self.Authors()
        if authors:
            return authors.split(", ")

    @property
    def main_template(self):
        return (
            Acquisition.aq_parent(self)
            .unrestrictedTraverse('main_template')
            .__of__(self)
        )
