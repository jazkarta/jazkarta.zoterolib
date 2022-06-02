import email
import quopri
import time
from email.header import Header
from datetime import timedelta
from celery.utils.log import get_task_logger
from collective.celery import task
from collective.celery import utils
from plone import api
from plone.registry.interfaces import IRegistry
from Products.CMFPlone.interfaces.controlpanel import IMailSchema
from Products.CMFPlone.utils import safe_encode
from pyzotero import zotero
from zope.component import getUtility

logger = get_task_logger(__name__)


# patch default celery serializers
utils._defaults["task_serializer"] = "json"
utils._defaults["result_serializer"] = "json"
utils._defaults["accept_content"] = ["application/json"]


@task()
def index_zotero_items(
    library_obj, start, batch_size, index_next=True, orig_start=None
):
    """
    Index all elements in a Zotero library in batches of the given size.
    After completion, if there are more items to index, the same task
    will be invoked with the same batch_size and an increased start,
    so that all objects will be eventually indexed. Sends an email
    when all indexing is complete.
    """
    if not orig_start:
        orig_start = time.time()
    zotero_api = zotero.Zotero(
        library_obj.zotero_library_id, library_obj.zotero_library_type
    )
    next = start + batch_size
    page = int(next / batch_size)
    current_batch = zotero_api.items(
        start=start,
        limit=batch_size,
        include="data,bib,citation",
        style=library_obj.citation_style,
    )
    logger.info(
        "Fetching page {} from Zotero Library {} %s".format(page, library_obj.id)
    )
    for item in current_batch:
        library_obj.index_element(item)

    if index_next and "next" in zotero_api.links:
        index_zotero_items.delay(
            library_obj, next, batch_size, index_next=index_next, orig_start=orig_start
        )
    else:
        send_mail.delay(
            subject=u'Zotero Library Indexing Completed',
            message=u'Finished indexing {} items in {} on the Zotero Library at {}.'.format(
                start + len(current_batch),
                library_obj.absolute_url(),
                str(timedelta(seconds=round(time.time() - orig_start))),
            ),
        )


@task.as_admin()
def send_mail(subject, message, mfrom=None, mto=None):
    portal = api.portal.get()
    message = safe_encode(message)
    msg = email.message_from_string(message)
    msg.set_charset('utf-8')

    registry = getUtility(IRegistry)
    settings = registry.forInterface(IMailSchema, False, prefix='plone')
    site_name = safe_encode(getattr(settings, 'email_from_name'))
    site_from = safe_encode(getattr(settings, 'email_from_address'))
    site_mfrom = email.utils.formataddr((site_name, site_from))

    if mfrom is not None:
        mfrom = safe_encode(mfrom)
        msg['Reply-To'] = Header(quopri.encodestring(mfrom, True))
    else:
        mfrom = site_mfrom

    # Send to portal email address if no recipient was specified, or if we're on a test site
    if mto is None:
        mto = site_mfrom

    mailhost = portal.MailHost
    mailhost.send(msg, subject=subject, mfrom=mfrom, mto=mto, charset='utf-8')
