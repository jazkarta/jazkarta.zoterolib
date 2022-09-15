import time
import z3c.form
from datetime import timedelta
from plone import api
from Products.CMFCore.utils import _checkPermission
from Products.Five.browser import BrowserView
from zExceptions import Forbidden
from zExceptions import NotFound
from zope.component import queryMultiAdapter
from zope.interface import implementer
from zope.location.interfaces import LocationError
from zope.publisher.interfaces import IPublishTraverse
from zope.traversing.namespace import view as ViewTraverser
from jazkarta.zoterolib.content.zotero_library import BrainProxy
from jazkarta.zoterolib import _

try:
    from jazkarta.zoterolib.tasks import index_zotero_items
    from jazkarta.zoterolib.tasks import remove_recently_deleted

    has_celery = True
except ImportError:
    has_celery = False

try:
    from Products.RedirectionTool.permissions import ModifyAliases
except ImportError:
    ModifyAliases = 'Impossible Permission that nobody has'


@implementer(IPublishTraverse)
class ZoteroItemView(BrowserView):
    """Traversal view to render a single Zotero record"""

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

    def can_set_aliases(self):
        return _checkPermission(ModifyAliases, self.context)

    def __call__(self, *args, **kw):
        self.item = self.fetch_item_for_path()
        # Raise a 404 when the object doesn't exist
        if self.item is None:
            raise NotFound
        return self.index(*args, **kw)


class ZoteroItemViewTraverser(ViewTraverser):
    def traverse(self, name, ignored):
        context = self.context.fetch_item_for_path()
        view = queryMultiAdapter((context, self.request), name=name)
        if view is None:
            raise LocationError(context, name)

        return view.__of__(context)


class UpdateLibraryForm(z3c.form.form.Form):
    """Simple form to update the zotero library"""

    label = _(u'Update All Zotero Library References')
    method = 'POST'
    enableCSRFProtection = True
    ignoreContext = False
    batch_size = 50

    fields = z3c.form.field.Fields()

    def _resumable(self):
        return getattr(self.context, '_async_zotero_resume', None) is not None

    def clear_resume(self):
        if getattr(self.context, '_async_zotero_resume', None) is not None:
            del self.context._async_zotero_resume
            self.actions.update()

    @z3c.form.button.buttonAndHandler(
        _(u'Resume Library Indexing'), condition=_resumable
    )
    def handleResume(self, action):
        self.handleUpdate.func(self, action)
        self.clear_resume()
        self.status = _(
            u"Resumed indexing Zotero Library. You will recieve an email when indexing is completed."
        )

    def updateActions(self):
        super(UpdateLibraryForm, self).updateActions()
        self.actions['clear-and-update-library'].klass += u' destructive'

    @z3c.form.button.buttonAndHandler(
        title=_(u'Update Library'), __name__='update-library'
    )
    def handleUpdate(self, action):
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            raise Forbidden('Request must be POST')
        if has_celery:
            last_version = self.context.last_modified_version
            remove_recently_deleted.delay(self.context, since=last_version)
            index_zotero_items.delay(
                self.context,
                start=0,
                batch_size=self.batch_size,
                since=last_version,
            )
            if last_version:
                if self._resumable:
                    self.clear_resume()
                self.status = _(
                    u"Started updating Zotero Library. Updates since version %s will be fetched. You will recieve an email when indexing is completed."
                    % last_version
                )
            else:
                self.status = _(
                    u"Started updating Zotero Library. All items be fetched. You will recieve an email when indexing is completed."
                )
        else:
            start_time = time.time()
            counts = self.context.update_items()
            self.status = _(
                u"Indexed {} and removed {} items from Zotero in {}".format(
                    counts['updated'],
                    counts['removed'],
                    str(timedelta(seconds=round(time.time() - start_time))),
                )
            )

    @z3c.form.button.buttonAndHandler(
        title=_(u'Clear and Update Library'), __name__='clear-and-update-library'
    )
    def handleClearAndUpdate(self, action):
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            raise Forbidden('Request must be POST')
        self.clear_resume()
        self.context.clear_items()
        if has_celery:
            index_zotero_items.delay(self.context, 0, self.batch_size)
            self.status = _(
                u"Started indexing Zotero Library. You will recieve an email when indexing is completed."
            )
        else:
            start_time = time.time()
            count = self.context.fetch_and_index_items()
            self.status = _(
                u"Updated {} items from Zotero in {}".format(
                    count, str(timedelta(seconds=round(time.time() - start_time)))
                )
            )


# Uncomment this to use eager mode (tasks are run inside the http server thread)
# Useful for debugging
# from collective.celery.utils import getCelery
# getCelery().conf.task_always_eager = True
