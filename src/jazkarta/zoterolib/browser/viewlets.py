from plone.app.layout.viewlets.common import DublinCoreViewlet
from plone.app.layout.viewlets.common import TitleViewlet
from Products.CMFCore.utils import getToolByName
from ..utils import html_to_plain_text


class ZoteroItemTitleViewlet(TitleViewlet):
    @property
    def page_title(self):
        item = self.context
        title = item.citationLabel
        if title:
            title = html_to_plain_text(title)
        else:
            title = item.title
        return title + self.sep + self.context.title


class ZoteroItemDublinCoreViewlet(DublinCoreViewlet):
    def update(self):
        plone_utils = getToolByName(self.context, 'plone_utils')
        context = self.context
        self.metatags = plone_utils.listMetaTags(context).items()
