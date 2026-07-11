"""Pytest bootstrap for the Complisoc test suite.

The production code is imported as ``complisoc.backend...``. That means the
*directory that contains the ``complisoc`` package* (its parent, e.g. the
repository root's parent, or the checked-out folder name on CI) must be on
``sys.path``.

This conftest inserts that parent directory at the front of ``sys.path`` so
the suite is collectable whether it is run from the repository root
(``python -m pytest`` inside ``complisoc/``) or from any parent folder.
It does not import any application code, so it cannot affect test behaviour.
"""
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parent  # .../complisoc
_PROJECT_PARENT = str(_REPO_ROOT.parent)

if _PROJECT_PARENT not in sys.path:
    sys.path.insert(0, _PROJECT_PARENT)
