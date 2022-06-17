import email
import quopri
import time
import transaction
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
from pyzotero.zotero_errors import HTTPError
from requests.exceptions import RequestException
from zope.component import getUtility

from .utils import get_user_email

logger = get_task_logger(__name__)


# patch default celery serializers
utils._defaults["task_serializer"] = "json"
utils._defaults["result_serializer"] = "json"
utils._defaults["accept_content"] = ["application/json"]


@task(bind=True, autoretry_for=(HTTPError,), retry_backoff=30, max_retries=4)
def index_zotero_items(
    self,
    library_obj,
    start,
    batch_size,
    index_next=True,
    orig_start_time=None,
    stop_at_date="",
):
    """
    Index all elements in a Zotero library in batches of the given size.
    After completion, if there are more items to index, the same task
    will be invoked with the same batch_size and an increased start,
    so that all objects will be eventually indexed. Sends an email
    when all indexing is complete.
    """
    # Always delete the resume marker on a new run
    if getattr(library_obj, '_async_zotero_resume', None) is not None:
        del library_obj._async_zotero_resume

    if not orig_start_time:
        orig_start_time = time.time()

    zotero_api = zotero.Zotero(
        library_obj.zotero_library_id, library_obj.zotero_library_type
    )
    next = start + batch_size
    page = int(next / batch_size)
    logger.info(
        "Fetching page {} from Zotero Library {}.".format(
            page, library_obj.zotero_library_id
        )
    )
    try:
        current_batch = zotero_api.items(
            start=start,
            limit=batch_size,
            include="data,bib,citation",
            style=library_obj.citation_style,
            sort="dateModified",
        )
    except (HTTPError, RequestException):
        logger.warn(
            "HTTPError while requesting page {} of Zotero library {}.".format(
                page, library_obj.zotero_library_id
            )
        )
        if self.request.retries >= self.max_retries:
            transaction.abort()
            # Set the resume point, send email, and commit
            library_obj._async_zotero_resume = start
            send_mail.delay(
                subject=u'Error Indexing Zotero Library',
                message=u'Zotero returned HTTPError on page {} on library {}. This was most likely the result of a temporary issue with the Zotero API, you can resume indexing at {}'.format(
                    page,
                    library_obj.zotero_library_id,
                    library_obj.absolute_url() + '/update-items',
                ),
                mto=get_user_email(),
            )
            transaction.commit()
        raise
    for item in current_batch:
        library_obj.index_element(item)
        if item["data"]["dateModified"] < stop_at_date:
            # In this case we finish updating the catalog with objects already fetched,
            # but prevent the next run from happening
            index_next = False

    if index_next and "next" in zotero_api.links:
        # The API response may have asked us to back-off. Respect it.
        wait_time = 0
        if zotero_api.backoff:
            # Wait 10 more seconds than requested, with a minimum of 10 seconds
            # just to be nice
            wait_time = max(round(zotero_api.backoff_duration - time.time()), 0) + 10
            logger.warn(
                "Got backoff response from from Zotero Library {}. Waiting {} seconds for next fetch.".format(
                    library_obj.zotero_library_id, wait_time
                )
            )

        index_zotero_items.apply_async(
            (library_obj, next, batch_size),
            {'index_next': index_next, 'orig_start_time': orig_start_time},
            countdown=max(wait_time, 0),
        )
    else:
        message = (
            u'Finished indexing {} items in {} on the Zotero Library at {}.'.format(
                start + len(current_batch),
                library_obj.absolute_url(),
                str(timedelta(seconds=round(time.time() - orig_start_time))),
            )
        )

        if stop_at_date:
            message += "\nItems modified after %s were updated".format(stop_at_date)
        send_mail.delay(
            subject=u'Zotero Library Indexing Completed',
            message=message,
            mto=get_user_email(),
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
