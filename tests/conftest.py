"""pytest bootstrap for the test suite.

The suite is written for ``python -m unittest discover -s tests``, which puts
``tests/`` on ``sys.path`` and imports every module by its bare name. pytest
imports the same files as the ``tests`` package instead, so the shared helpers
(``desktop_harness``) would not resolve. Putting ``tests/`` on ``sys.path`` here
makes both runners agree; Qt is forced offscreen so no display is needed.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)
