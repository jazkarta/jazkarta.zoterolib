from plone import api
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zExceptions import NotFound
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse


@implementer(IPublishTraverse)
class ZoteroItemView(BrowserView):
    """Traversal view to render a single Zotero record"""
    index = ViewPageTemplateFile('item_view.pt')
    item_path = ''
    brain = None

    def publishTraverse(self, request, name):
        self.item_path += '/' + name
        return self

    def __call__(self, *args, **kw):
        catalog = api.portal.get_tool('portal_catalog')
        catalog_item_path = (
            '/'.join(self.context.getPhysicalPath())
            + '/' + self.__name__
            + self.item_path
        )
        item_rid = catalog.getrid(catalog_item_path)
        # For now we raise 404 when the object doesn't exist, but it may make sense
        # to treat a missing path as a zotero collection path and search for items
        # within that path to construct a partial listing.
        if item_rid is None:
            raise NotFound
        self.brain = catalog._catalog[item_rid]
        return self.index(*args, **kw)
