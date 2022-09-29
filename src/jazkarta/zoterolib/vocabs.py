import gzip
import json
import os
from plone import api
from plone.app.vocabularies.types import BAD_TYPES
from Products.CMFPlone.utils import safe_unicode
from zope.interface import implementer
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary
from zope.schema.vocabulary import SimpleTerm


with gzip.open(
    os.path.join(os.path.dirname(__file__), "browser/static/styles.json.gz")
) as styles_file:
    styles_data = json.load(styles_file)

citations_vocab = SimpleVocabulary(
    [
        SimpleTerm(title=i["title"], value=i["name"], token=str(i["name"]))
        for i in styles_data
    ]
)

# Build a very simple text index of the style titles
citations_text_index = {}
for item in styles_data:
    for word in item["title"].lower().split():
        word = word.strip()
        if len(word) > 3:
            matches = citations_text_index.setdefault(word, [])
            matches.append(item["name"])


@implementer(IVocabularyFactory)
class SearchableCitationStylesVocabulary(object):
    items = citations_vocab

    def __call__(self, context, query=None):
        if query is None:
            return self.items
        term_matches = matches = set()
        words = query.split()
        for i, word in enumerate(words):
            word = word.lower().strip()
            if not word:
                continue
            term_matches.update(citations_text_index.get(word, []))
            # Treat the last word as a wildcard if we don't have a match
            if not term_matches and len(word) >= 3 and i == (len(words) - 1):
                for entry in citations_text_index:
                    if word in entry:
                        term_matches.update(citations_text_index.get(entry))
            if matches is not term_matches:
                matches = matches.intersection(term_matches)
            term_matches = set()
        terms = [self.items.getTerm(v) for v in matches]
        terms.sort(key=lambda t: t.title.lower())
        return SimpleVocabulary(terms)


CitationStylesVocabularyFactory = SearchableCitationStylesVocabulary()


@implementer(IVocabularyFactory)
class TypesTitlesVocabulary(object):
    bad_types = set(BAD_TYPES)

    def __call__(self, context):
        catalog = api.portal.get_tool('portal_catalog')
        titles = [
            t for t in catalog.uniqueValuesFor('Type') if t and t not in self.bad_types
        ]
        terms = [SimpleTerm(t, title=safe_unicode(t), token=t) for t in titles]
        terms.sort(key=lambda t: t.value)
        return SimpleVocabulary(terms)


TypesTitlesVocabularyFactory = TypesTitlesVocabulary()
