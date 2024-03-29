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
from Products.CMFPlone.utils import safe_nativestring
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
    since=0,
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
            direction="asc",
            since=since,
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
            library_obj._async_zotero_resume = True
            send_mail.delay(
                subject=u'Error Indexing Zotero Library',
                message=u'Zotero returned HTTPError on page {} on library {}. This was most likely the result of a temporary issue with the Zotero API, you can resume indexing at {}'.format(
                    page,
                    library_obj.zotero_library_id,
                    content_path(library_obj) + '/update-items',
                ),
                mto=get_user_email(),
            )
            transaction.commit()
        raise
    count = 0
    for item in current_batch:
        library_obj.index_element(item)
        count += 1
    if count:
        # Store the version id of the most recent indexed object as the current
        # library version id.
        library_obj.update_modified_version(current_batch[-1]["version"])

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
            {
                'index_next': index_next,
                'orig_start_time': orig_start_time,
                'since': since,
            },
            countdown=max(wait_time, 0),
        )
    else:
        library_obj.update_modified_version()
        message = (
            u'Finished indexing {} items in {} from the Zotero Library at {}.'.format(
                start + count,
                str(timedelta(seconds=round(time.time() - orig_start_time))),
                content_path(library_obj),
            )
        )

        if since:
            message += "\nOnly items modified after version {} were updated".format(
                since
            )
        send_mail.delay(
            subject=u'Zotero Library Indexing Completed',
            message=message,
            mto=get_user_email(),
        )
    return {"updated": count}


@task(bind=True, autoretry_for=(HTTPError,), retry_backoff=30, max_retries=4)
def remove_recently_deleted(self, library_obj, since=None):
    count = library_obj.remove_recently_deleted(since=since)
    message = u'Removed {} items deleted since version {} from the Zotero Library at {}.'.format(
        count,
        since,
        content_path(library_obj),
    )
    send_mail.delay(
        subject=u'Removed Zotero Library Items',
        message=message,
        mto=get_user_email(),
    )
    return {"removed": count}


@task.as_admin()
def send_mail(subject, message, mfrom=None, mto=None):
    portal = api.portal.get()
    message = safe_nativestring(message)
    msg = email.message_from_string(message)
    msg.set_charset('utf-8')

    registry = getUtility(IRegistry)
    settings = registry.forInterface(IMailSchema, False, prefix='plone')
    site_name = safe_nativestring(getattr(settings, 'email_from_name'))
    site_from = safe_nativestring(getattr(settings, 'email_from_address'))
    site_mfrom = email.utils.formataddr((site_name, site_from))

    if mfrom is not None:
        mfrom = safe_nativestring(mfrom)
        msg['Reply-To'] = Header(quopri.encodestring(mfrom, True))
    else:
        mfrom = site_mfrom

    # Send to portal email address if no recipient was specified, or if we're on a test site
    if mto is None:
        mto = site_mfrom

    mailhost = portal.MailHost
    mailhost.send(msg, subject=subject, mfrom=mfrom, mto=mto, charset='utf-8')


def content_path(obj):
    portal_path = obj.unrestrictedTraverse(
        '@@plone_portal_state'
    ).navigation_root_path()
    obj_path = '/'.join(obj.getPhysicalPath())
    return obj_path[len(portal_path) :]
