from plone.app.contentlisting.catalog import CatalogContentListingObject
from jazkarta.zoterolib.utils import html_to_plain_text


class ZoteroAwareCatalogContentListingObject(CatalogContentListingObject):
    def Description(self):
        description = self._brain.Description
        if self._brain.portal_type == 'ExternalZoteroItem':
            return html_to_plain_text(self._brain.Description)

        return description
