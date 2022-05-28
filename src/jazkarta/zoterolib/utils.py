import re

try:
    from html import unescape
except ImportError:
    from HTMLParser import HTMLParser

    unescape = HTMLParser().unescape
from plone import api
from Products.CMFPlone.log import log_exc
from Products.CMFPlone.utils import safe_encode, safe_unicode

TAG_RE = re.compile('</?.+?/?>')


def html_to_plain_text(text):
    if not text:
        return ''
    text = unescape(text)
    transformer = api.portal.get_tool('portal_transforms')
    encoded = safe_encode(text)
    try:
        stream = transformer.convertTo('text/plain', encoded, mimetype='text/html')
        text = stream.getData().strip()
    except (ValueError, UnicodeError):
        log_exc('Error converting HTML to plain text: {}'.format(text))
        text = TAG_RE.sub(' ', encoded).strip()

    return safe_unicode(text)


def camel_case_splitter(text):
    matches = re.finditer(
        r'.+?(?:(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z0-9])|$)', text
    )
    return ' '.join(m.group(0).capitalize() for m in matches)
