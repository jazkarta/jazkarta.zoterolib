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
and display them as a list or on a faceted search.


Features
--------

- Provides a Dexterity content type called Zotero Library that can be added to the site and configured with a Zotero Library ID, 
  Zotero Library Type (user or group) and Citation Style Format. 
- Provides an action called Update Zotero Library Items which provides 2 buttons:

  - Update Library - Fetch items from the Zotero library that have been added since the last update. This includes deletion of 
    items that have been removed from the library (including those that are in the trash). Bibliographic metadata and the formatted 
    citation are retrieved via the Zotero API and indexed in the Zope catalog. No additional content items are created.
    All Zotero creatorTypes (author, editor, translator, contributor, etc.) are added to the Author index.
  - Clear and Update Library - Clear all items and re-download and index everything. This button is red because for large libraries it is 
    RAM intensive and can take a lot of time during which the library will be incomplete as it builds itself back up from scratch.
    
- Optionally can perform the update functions asynchronously using Celery. See below for how to integrate this add-on
  with Celery.
- Provides a list view of all references in the Zotero library, formatted in the appropriate Citation Style.
- Optionally can provide a faceted search view of the references in the Zotero library. See below for how to integrate this add-on
  with eea.facetednavigation.
- Provides an item view of an individual reference, formatted in the appropriate Citation Style. A link to view the item in Zotero is 
  also provided.

NOTE: If the citation style is changed on the Zotero Library, it is necessary to run Clear and Update Library to refresh all the 
records and see the new style, since formatted records are pulled in directly from the Zotero API.

Need to add

- Integration with Celery - optional? Instructions to add?
- Integration with faceted nav - optional? Instructions to add?
- Add something about how to customize what metadata fields to index?
- What does the default (no faceted nav) view of a Zotero Library look like? A list in what order?
- Not sure how much of the reference view is part of the add-on and how much is UMP (Return to Listing, Aliases, tags linked back to search)


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

Built by `Jazkarta <https://jazkarta.com>`_.

- Alec Mitchell (initial author)
- Witek
- Silvio Tomatis

