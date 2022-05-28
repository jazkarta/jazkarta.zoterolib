import time
import z3c.form
from datetime import timedelta
from plone import api
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zExceptions import Forbidden
from zExceptions import NotFound
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse
from jazkarta.zoterolib.content.zotero_library import BrainProxy
from jazkarta.zoterolib import _


@implementer(IPublishTraverse)
class ZoteroItemView(BrowserView):
    """Traversal view to render a single Zotero record"""

    index = ViewPageTemplateFile("item_view.pt")
    item_path = ""
    item = None

    def __init__(self, context, request=None):
        self.context = context
        self.request = request

    def fetch_item_for_path(self, path=None):
        catalog = api.portal.get_tool("portal_catalog")
        if path is None:
            path = self.item_path
        catalog_item_path = (
            "/".join(self.context.getPhysicalPath()) + "/" + self.__name__ + path
        )
        item_rid = catalog.getrid(catalog_item_path)
        if item_rid is None:
            return None
        return BrainProxy(catalog._catalog[item_rid], self.context).__of__(self.context)

    def publishTraverse(self, request, name):
        self.item_path += "/" + name
        return self

    def unrestrictedTraverse(self, path):
        obj = self
        if hasattr(path, "split"):
            path = path.split("/")
        for name in path:
            obj = obj.__bobo_traverse__(self.request, name)
        if obj is self:
            raise AttributeError(name)
        return obj

    restrictedTraverse = unrestrictedTraverse

    def __bobo_traverse__(self, request, name):
        __traceback_info__ = (self.context, name)
        self.item_path += "/" + name
        # Get the catalog brain once we've found something
        item = self.fetch_item_for_path()
        if item is None:
            return self
        return item

    def __call__(self, *args, **kw):
        self.item = self.fetch_item_for_path()
        # Raise a 404 when the object doesn't exist
        if self.item is None:
            raise NotFound
        return self.index(*args, **kw)


class UpdateLibraryForm(z3c.form.form.Form):
    """Simple form to update the zotero library"""

    label = _(u'Update All Zotero Library References')
    method = 'POST'
    enableCSRFProtection = True
    ignoreContext = False

    fields = z3c.form.field.Fields()

    @z3c.form.button.buttonAndHandler(_(u'Update Library'))
    def handleUpdate(self, action):
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            raise Forbidden('Request must be POST')
        start_time = time.time()
        self.context.clear_items()
        count = self.context.fetch_and_index_items()
        self.status = _(
            u"Updated {} items from Zotero in {}".format(
                count, str(timedelta(seconds=round(time.time() - start_time)))
            )
        )
