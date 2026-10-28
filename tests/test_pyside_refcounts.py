"""Catch Qt binding regressions that can terminate Python before 3.12."""
import sys
import unittest

from PySide6.QtGui import QColor


@unittest.skipUnless(sys.implementation.name == "cpython" and sys.version_info < (3, 12),
                     "None has an immortal reference count on newer CPython")
class PySideRefcountTests(unittest.TestCase):
    def test_void_qt_calls_do_not_consume_none_references(self):
        color = QColor("red")
        color.setAlpha(10)  # Warm up the binding before measuring.
        before = sys.getrefcount(None)
        for _ in range(256):
            color.setAlpha(10)
        after = sys.getrefcount(None)
        self.assertGreaterEqual(after, before - 10,
                                "Qt calls unexpectedly consumed references to None")

