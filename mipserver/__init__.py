"""mipserver — a MicroPython ``mip`` package index served from GitHub repositories.

The package implements the ``micropython.org/pi/v2`` protocol that the ``mip``
client on a device speaks:

* :mod:`mipserver.app` holds the FastAPI application and the HTTP routes.
* :mod:`mipserver.Helper` does the actual work: git checkouts, ``mpy-cross``
  compilation and the content-addressed file store.
* :mod:`mipserver.config` builds the :data:`mipserver.config.settings` singleton
  and configures logging as an import side effect.
* :mod:`mipserver.datastructures` contains the request/response models and the
  shared type aliases.

``app`` is deliberately not re-exported here: importing it would drag the whole
FastAPI application (and its cache-directory side effects) into every import of
this package. Use ``from mipserver.app import app`` instead.
"""
