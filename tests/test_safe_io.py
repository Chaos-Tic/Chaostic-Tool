"""Shared symlink-safe / atomic result writer (core.safe_io) and its adoption.

ChaosticTool's CLI runs under sudo while results land in a user-owned tree, so a
planted symlink at a destination — or a symlinked parent directory — must never
redirect a root write (CWE-59), and a reader must never see a half-written file
(atomicity). These tests pin the primitive and spot-check the writers routed
through it (mission report, scope cache, Henon export).
"""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from core import report, safe_io
from core import target as tgt


class SafeIoPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="chaostic-safeio-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def test_atomic_write_roundtrip_text_and_bytes(self):
        p = self.tmp / "a.txt"
        safe_io.atomic_write(p, "héllo\n")
        self.assertEqual(p.read_text(encoding="utf-8"), "héllo\n")
        safe_io.atomic_write(p, b"\x00\x01rawbytes")
        self.assertEqual(p.read_bytes(), b"\x00\x01rawbytes")

    def test_atomic_write_replaces_a_symlinked_destination_without_following(self):
        # os.replace swaps the name; the symlink target must stay untouched.
        victim = self.tmp / "victim.txt"
        victim.write_text("KEEP", encoding="utf-8")
        dest = self.tmp / "dest.txt"
        dest.symlink_to(victim)
        safe_io.atomic_write(dest, "new content")
        self.assertFalse(dest.is_symlink())
        self.assertEqual(victim.read_text(encoding="utf-8"), "KEEP")
        self.assertEqual(dest.read_text(encoding="utf-8"), "new content")

    def test_atomic_write_refuses_symlinked_parent_under_root(self):
        root = self.tmp / "root"
        root.mkdir()
        outside = self.tmp / "outside"
        outside.mkdir()
        (root / "sub").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            safe_io.atomic_write(root / "sub" / "f.txt", "x", within=root)
        self.assertFalse((outside / "f.txt").exists())

    def test_atomic_write_leaves_no_temp_file_behind(self):
        p = self.tmp / "clean.txt"
        safe_io.atomic_write(p, "ok")
        leftovers = [q.name for q in self.tmp.iterdir() if q.name != "clean.txt"]
        self.assertEqual(leftovers, [], f"stray temp files: {leftovers}")

    def test_atomic_copyfileobj_text_preserves_content(self):
        src = io.StringIO("line1\nline2\n")
        p = self.tmp / "copy.txt"
        safe_io.atomic_copyfileobj(src, p, text=True)
        self.assertEqual(p.read_text(encoding="utf-8"), "line1\nline2\n")

    def test_reject_symlinked_parent_rejects_escape(self):
        root = self.tmp / "r"
        root.mkdir()
        with self.assertRaises(OSError):
            safe_io.reject_symlinked_parent(root, self.tmp / "elsewhere" / "f.txt")

    def test_atomic_write_refuses_symlinked_root_itself(self):
        # The `within` root being a symlink is refused (CWE-59): O_NOFOLLOW on the
        # dir_fd descent, and an explicit lstat on the name-based fallback.
        real = self.tmp / "real_root"
        real.mkdir()
        link_root = self.tmp / "link_root"
        link_root.symlink_to(real, target_is_directory=True)
        with self.assertRaises(OSError):
            safe_io.atomic_write(link_root / "sub" / "f.txt", "x", within=link_root)
        self.assertFalse((real / "sub").exists())

    def test_atomic_write_creates_nested_dirs_under_root(self):
        root = self.tmp / "tree"
        root.mkdir()
        out = root / "a" / "b" / "f.json"
        safe_io.atomic_write(out, '{"ok": true}', within=root)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8")), {"ok": True})

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "mode bits are POSIX")
    def test_atomic_write_result_is_not_world_readable(self):
        # Result files can hold recon data; the written file must be 0o600
        # whichever path (dir_fd or fallback) produced it (CWE-732).
        root = self.tmp / "t2"
        root.mkdir()
        inside = root / "sub" / "f.txt"
        safe_io.atomic_write(inside, "secret-ish", within=root)
        self.assertEqual(inside.stat().st_mode & 0o777, 0o600)
        outside = self.tmp / "o.txt"
        safe_io.atomic_write(outside, "x")  # fallback (within=None)
        self.assertEqual(outside.stat().st_mode & 0o777, 0o600)

    def test_results_root_membership(self):
        saved = tgt.TARGETS_ROOT
        try:
            tgt.TARGETS_ROOT = self.tmp / "targets"
            inside = tgt.TARGETS_ROOT / "example.com" / "recon" / "nmap.txt"
            outside = self.tmp / "elsewhere" / "x.txt"
            self.assertEqual(safe_io.results_root(inside), tgt.TARGETS_ROOT)
            self.assertIsNone(safe_io.results_root(outside))
        finally:
            tgt.TARGETS_ROOT = saved

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "O_NOFOLLOW is POSIX-only")
    def test_open_nofollow_refuses_symlinked_final_component(self):
        victim = self.tmp / "v2.txt"
        victim.write_text("KEEP", encoding="utf-8")
        dest = self.tmp / "log.txt"
        dest.symlink_to(victim)
        with self.assertRaises(OSError):
            safe_io.open_nofollow(dest)
        self.assertEqual(victim.read_text(encoding="utf-8"), "KEEP")

    def test_open_nofollow_writes_and_appends(self):
        p = self.tmp / "stream.txt"
        with safe_io.open_nofollow(p, "w") as fh:
            fh.write("a")
        with safe_io.open_nofollow(p, "a") as fh:
            fh.write("b")
        self.assertEqual(p.read_text(encoding="utf-8"), "ab")


class ReportWriterSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="chaostic-safeio-report-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def _report(self):
        return report.MissionReport(target="example.com", host="example.com",
                                    url="https://example.com")

    def test_write_report_atomic_and_symlink_replace(self):
        victim = self.tmp / "keep.md"
        victim.write_text("KEEP", encoding="utf-8")
        dest = self.tmp / "report.md"
        dest.symlink_to(victim)
        out = report.write_report(self._report(), dest, fmt="md")
        self.assertFalse(Path(out).is_symlink())
        self.assertEqual(victim.read_text(encoding="utf-8"), "KEEP")
        self.assertTrue(Path(out).read_text(encoding="utf-8"))

    def test_write_report_refuses_symlinked_parent(self):
        root = self.tmp / "targets"
        root.mkdir()
        outside = self.tmp / "evil"
        outside.mkdir()
        (root / "example.com").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            report.write_report(self._report(), root / "example.com" / "r.md",
                                fmt="md", within=root)


class ScopeCacheSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="chaostic-safeio-scope-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self._root = tgt.TARGETS_ROOT
        self._target = dict(tgt.TARGET)
        self._scope = dict(tgt.SCOPE)
        tgt.TARGETS_ROOT = self.tmp / "targets"
        tgt.TARGET.update(host="example.com", url="https://example.com", port="443")
        tgt.SCOPE.update(include_subdomains=True, subdomains=["api.example.com"], excluded=[])

        def restore():
            tgt.TARGETS_ROOT = self._root
            tgt.TARGET.clear(); tgt.TARGET.update(self._target)
            tgt.SCOPE.clear(); tgt.SCOPE.update(self._scope)
        self.addCleanup(restore)

    def test_save_scope_writes_atomically(self):
        tgt.save_scope()
        cache = tgt.target_dir() / "subdomains.json"
        self.assertTrue(cache.exists())
        data = json.loads(cache.read_text(encoding="utf-8"))
        self.assertEqual(data["subdomains"], ["api.example.com"])


if __name__ == "__main__":
    unittest.main()
