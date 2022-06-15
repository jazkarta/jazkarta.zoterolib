from DateTime import DateTime
from eea.facetednavigation.interfaces import IQueryWillBeExecutedEvent
from zope.component import adapter
from .content.zotero_library import IZoteroLibrary


@adapter(IZoteroLibrary, IQueryWillBeExecutedEvent)
def modify_eea_query(context, event):
    query = event.query
    base_query = event.object.query()
    for key in base_query:
        if not query.get(key):
            query[key] = base_query[key]

    # Only include items with a date set
    if 'effective' not in query:
        query['effective'] = {'query': DateTime('9999999-01-01'), 'range': 'max'}
