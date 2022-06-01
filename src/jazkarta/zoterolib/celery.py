"""Module to host celery tasks
"""
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import noSecurityManager
from celery import Celery, Task
from Testing.makerequest import makerequest
from zExceptions.ExceptionFormatter import format_exception
from ZODB.POSException import ConflictError
from zope.component.hooks import setSite
from zope.event import notify
from zope.app.publication.interfaces import BeforeTraverseEvent
import logging
import os
import sys
import transaction
import Zope2


BROKER = os.environ.get('BROKER_URI', 'redis://localhost//')
CELERY_QUEUE_NAME = os.environ.get('CELERY_QUEUE_NAME', 'jazkarta.zoterolib.tasks')
celery = Celery(CELERY_QUEUE_NAME, broker=BROKER, backend=BROKER)
logger = logging.getLogger(__name__)


class AfterCommitTask(Task):
    """Base for tasks that queue themselves after commit.

    This is intended for tasks scheduled from inside Zope.
    """

    abstract = True

    # Override apply_async to register an after-commit hook
    # instead of queueing the task right away.
    def apply_async(self, *args, **kw):
        def hook(success):
            if success:
                super(AfterCommitTask, self).apply_async(*args, **kw)

        transaction.get().addAfterCommitHook(hook)
        # apply_async normally returns a deferred result object,
        # but we don't have one available yet


def after_commit_task(func):
    """Decorator to help write tasks that get queued after commit."""
    return celery.task(base=AfterCommitTask)(func)


def zope_task(**task_kw):
    """Decorator of celery tasks that should be run in a Zope context.

    The decorator function takes a path as a first argument,
    and will take care of traversing to it and passing it
    (presumably a portal) as the first argument to the decorated function.

    Also takes care of initializing the Zope environment,
    running the task within a transaction, and retrying on
    ZODB conflict errors.
    """

    def wrap(func):
        def new_func(*args, **kw):
            site_path = kw.get('site_path', 'Plone')
            site_path = site_path.strip().strip('/')

            # This is a super ugly way of getting Zope to configure itself
            # from the main instance's zope.conf. XXX FIXME
            sys.argv = ['']
            os.environ['ZOPE_CONFIG'] = 'parts/client1/etc/zope.conf'
            try:
                app = makerequest(Zope2.app())
            except:
                t, v, tb = sys.exc_info()
                logger.error(''.join(format_exception(t, v, tb)))
                raise

            transaction.begin()

            try:
                try:
                    # find site
                    site = app.unrestrictedTraverse(site_path)
                    # fire traversal event so various things get set up
                    notify(BeforeTraverseEvent(site, site.REQUEST))

                    # set up admin user
                    user = app.acl_users.getUserById('admin')
                    newSecurityManager(None, user)

                    # run the task
                    result = func(site, *args, **kw)

                    # commit transaction
                    transaction.commit()
                except ConflictError as e:
                    # On ZODB conflicts, retry using celery's mechanism
                    transaction.abort()
                    raise new_func.task.retry(exc=e)
                except:
                    transaction.abort()
                    raise
            finally:
                noSecurityManager()
                setSite(None)
                app._p_jar.close()

            return result

        new_func.__name__ = func.__name__
        task = celery.task(**task_kw)(new_func)
        new_func.task = task
        return task

    return wrap


@zope_task()
def index_zotero_library(library_obj, start=0, batch_size=100):
    """
    Index all elements in a Zotero library in batches of the given size.
    After completion, if there are more items to index, the same task
    will be invoked with the same batch_size and an increased start,
    so that all objects will be eventually indexed.
    """
    logger.info("Fetching all items from Zotero library %s" % library_obj.id)
