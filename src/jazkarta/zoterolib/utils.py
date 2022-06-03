import email
import re
import six

try:
    from html import unescape
except ImportError:
    from HTMLParser import HTMLParser

    unescape = HTMLParser().unescape
from plone import api
from Products.CMFPlone.log import log_exc
from Products.CMFPlone.utils import safe_encode, safe_unicode

TAG_RE = re.compile('</?.+?/?>')


def plone_encode(val):
    """In Plone on Python 2, some catalog indexes expect encoded values"""
    if not six.PY3:
        return safe_encode(val)
    return val


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


def get_user_email():
    user = api.user.get_current()
    if user is not None:
        address = user.getProperty('email', None)
        fullname = user.getProperty('fullname', None)
        if fullname and address:
            address = email.utils.formataddr((fullname, address))
        return address or None
