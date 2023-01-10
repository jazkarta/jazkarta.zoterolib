.. This README is meant for consumption by humans and pypi. Pypi can render rst files so please do not use Sphinx features.
   If you want to learn more about writing documentation, please check out: http://docs.plone.org/about/documentation_styleguide.html
   This text does not appear on pypi or github. It is a comment.

.. image:: https://travis-ci.org/collective/jazkarta.zoterolib.svg?branch=master
    :target: https://travis-ci.org/collective/jazkarta.zoterolib

.. image:: https://coveralls.io/repos/github/collective/jazkarta.zoterolib/badge.svg?branch=master
    :target: https://coveralls.io/github/collective/jazkarta.zoterolib?branch=master
    :alt: Coveralls

.. image:: https://img.shields.io/pypi/v/jazkarta.zoterolib.svg
    :target: https://pypi.python.org/pypi/jazkarta.zoterolib/
    :alt: Latest Version

.. image:: https://img.shields.io/pypi/status/jazkarta.zoterolib.svg
    :target: https://pypi.python.org/pypi/jazkarta.zoterolib
    :alt: Egg Status

.. image:: https://img.shields.io/pypi/pyversions/jazkarta.zoterolib.svg?style=plastic   :alt: Supported - Python Versions

.. image:: https://img.shields.io/pypi/l/jazkarta.zoterolib.svg
    :target: https://pypi.python.org/pypi/jazkarta.zoterolib/
    :alt: License


==================
jazkarta.zoterolib
==================

This add-on lets you embed a `Zotero <https://www.zotero.org/>`_ library of bibliographic references in your `Plone <http://plone.org>`_ site 
and display them in listings or on a faceted search.


Features
--------

- Provides a Dexterity content type called Zotero Library that can be added to
  the site and configured with a Zotero Library ID, Zotero Library Type (user or
  group) and Citation Style Format.
- Zotero library items are indexed in the ``portal_catalog`` and can appear in
  listings and searches. The add-on includes custom indexes and metadata for
  bibiographic items. This includes various "author" indexes which incorporate
  all Zotero ``creatorType`` values (e.g. author, editor, translator,
  contributor, etc.)
- The Zotero Library provides an action called Update Zotero Library Items with
  two buttons:

  - Update Library - Fetch items from the Zotero library that have been added
    since the last update. This includes deleting items that have been removed
    from the library (including those that are in the trash). Bibliographic data
    and the formatted citation are retrieved via the Zotero API and indexed in
    the ``portal_catalog``.
  - Clear and Update Library - Clear all bibliographic references from the
    ``portal_catalog`` and re-fetch and index them. This button is red because
    for large libraries it is RAM intensive and can take a lot of time during
    which the library will be incomplete as it builds itself back up from
    scratch. This should only be necessary after having e.g. changed the
    citation style for the library.

- Updates can optionally be performed asynchronously in batches using Celery.
  This is recommended when working with libraries containing more than a few hundred
  items. See below for how to integrate this add-on with Celery.
- Provides a paginated list view of all references in the Zotero library,
  formatted in the appropriate Citation Style.
- Individual bibliographic references are not represented by Plone content
  items. The Zotero Library provides an item view for individual
  references, which renders them in the chosen Citation Style. A link to view
  the item in Zotero is included in the item view.
- If ``Products.RedirectionTool`` is installed, redirects/aliases can be easily added
  for individual bibliographic reference views (for example when migrating from the 
  CMFBibliographyAT add-on).

REMEMBER: If the citation style is changed on the Zotero Library edit form, it is
necessary to run Clear and Update Library to refresh all the records and see the
new style, since the formatted records are pulled in directly from the Zotero
API.


Integration with Celery (optional)
----------------------------------

If you are using a large Zotero library, then library synchronization can take a
very long time which is likely to result in a ``ConflictError`` and failure to
sync. For libraries larger than a few hundred items, it is best to perform
library updates asynchronously.

This add-on integrates automatically with the `collective.celery
<https://pypi.python.org/project/collective.celery>`_ add-on. When
``collective.celery`` is installed in your buildout, the "Update Library" and
"Clear and Update Library" actions will run asnychronously using the Celery task
queue.

The asynchronous updates are processed in batches of 100, with retries on each
batch in the case of a ``ConflictError`` or service outage. Any failure to
complete a batch will result in an email to the administrator, and a "Resume"
button will appear on the "Update Zotero Library" form to allow resuming the
update.

Upon completion of the library sync, an email will be sent to the site contact
email indicating that the update has completed.


Integration with eea.facetednavigation (optional)
-------------------------------------------------

If the `eea.facetednavigation
<https://pypi.org/project/eea.facetednavigation/>`_ add-on is installed in your
Plone site, then you will be able to "Enable Faceted Navigation" on a Zotero
Library using the actions menu.

Each bibliographic reference is indexed in the ``portal_catalog`` and can be
discovered in faceted searches. Bibliographic references have a ``portal_type``
of "ExternalZoteroItem" and a variety of ``Type`` values (e.g. "Article
Reference", "Proceedings Reference", ...) which can be used for faceted search
filtering. Searches can be performed using the standard indexes (e.g. Title,
SearchableText, Subject, ...), and the add-on includes a few custom indexes
which can be used in faceted searches and collections:

- Author Search (Bibliography) - Full text search for authors/contributors
- Author (Bibliography) - Keyword search for exact author/contributor match
- Publication Year (Bibliography)
- Publication Date (Bibliography)
- Bibliographic Keywords - Same as Tags/Subjects, but limited to bibliographic
  items


Customization
-------------

You can add custom Plone indexers to index or store additional metadata for bibliographic
items. The objects indexed by the catalog have a ``zotero_item`` attribute which
contains the full Zotero API object for the bibliographic reference, and which
can be used by custom indexers.

The ``@@zotero_items`` view can be overridden to provide a customized
template/rendering of individual bibliographic references.

The ``@@view`` listing view can be overridden to provide a customized
template/rendering of the listing of bibliographic references.


Examples
--------

This add-on can be seen in action at the following sites:

- https://www.upress.umn.edu/test-division/bibliography/search


Installation
------------

Install jazkarta.zoterolib by adding it to your buildout::

    [buildout]

    ...

    eggs =
        jazkarta.zoterolib


and then running ``bin/buildout``


Contribute
----------

Make sure you install and activate `pre-commit` to ensure your code validates at each commit::

    pip install -r requirements-dev.txt
    pre-commit install

You can find the issue tracker and source code for this package at:

- Issue Tracker: https://github.com/Jazkarta/jazkarta.zoterolib/issues
- Source Code: https://github.com/Jazkarta/jazkarta.zoterolib


License
-------

The project is licensed under the GPLv2.


Credits
-------

Funded by the `University of Minnesota Press <https://www.upress.umn.edu>`_. Built by `Jazkarta <https://jazkarta.com>`_. Principal authors:

- Alec Mitchell
- Silvio Tomatis
