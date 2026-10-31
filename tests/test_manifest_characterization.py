"""Characterization: freeze the manifest's agreement with the real installers.

The A4 manifest (``core.tool_manifest``) is becoming the single source of
installation truth (chantier A4->A3). Before any wiring moves, this test pins
the manifest's current decision, per tool x platform, against the decisions the
running installers make today:

* portable artifacts against ``desktop/packages.json`` and the live resolution
  in ``desktop/packages.py`` (the data ``desktop/packages.py`` is about to read
  from the manifest instead);
* Linux distribution packages against the canonical ``PACKAGE_NAMES`` table and
  its standalone bridge copy in ``desktop/linux_install.py`` (the duplicated
  mapping that is about to be deduplicated);
* Linux automatic-vs-manual capability against the CLI engine
  ``core/installer.py``, whose per-binary tables classify each tool.

The test passes on the current tree: it records reality, it does not prescribe
it. Known, pre-existing divergences between the manifest and the CLI installer
are asserted explicitly so that a later change cannot erase them silently.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import core.installer as installer
import desktop.packages as packages
from core.tool_manifest import (
    PACKAGE_NAMES,
    PLATFORMS,
    TOOL_MANIFEST,
    TOOL_PACKAGE_ALIASES,
)
from core.tools import TOOLS
from desktop.linux_install import PACKAGE_NAMES as BRIDGE_PACKAGE_NAMES

_SPECS = json.loads((Path(installer.__file__).resolve().parents[1]
                     / "desktop" / "packages.json").read_text(encoding="utf-8"))
_ARCHIVE_METHODS = {"release", "file", "installer", "pip-source"}


def _resolve_like_packages_py(spec: dict, platform: str):
    """Resolve an artifact exactly as ``desktop/packages.py`` does at runtime.

    Returns ``(resolved_spec, binary)`` or ``None`` when the platform is not
    served, mirroring ``package_spec`` without raising.
    """
    spec = dict(spec)
    os_name = platform.split("-", 1)[0]
    if "artifacts" in spec:
        if platform not in spec["artifacts"]:
            return None
        spec.update(spec["artifacts"][platform])
    elif spec.get("platforms") and platform not in spec["platforms"]:
        return None
    by_os = spec.get("binary_by_os") or {}
    if os_name in by_os:
        binary = by_os[os_name]
    else:
        binary = spec["binary"] if os_name == "windows" else spec["binary"].removesuffix(".exe")
    return spec, binary


def _installer_auto_on_linux(binary: str) -> bool:
    """Whether ``core/installer.py`` can install ``binary`` automatically on Linux.

    Reads the engine's static data tables only; the live resolver
    (``_candidate_methods``) probes the host package manager and is not called.
    """
    pkg_tuple = installer.PKG_NAMES.get(binary)
    if pkg_tuple and any(pkg_tuple):
        return True
    tables = (
        installer.GO_MODULES, installer.CARGO_PACKAGES, installer.RELEASE_ASSETS,
        installer.PIPX_PACKAGES, installer.PIP_PACKAGES, installer.GEM_PACKAGES,
        installer.SOURCE_INSTALLS, installer.DIRECT_DOWNLOADS,
        installer.PYTHON_MODULE_WRAPPERS,
    )
    return any(binary in table and table[binary] for table in tables)


class ManifestCharacterizationTests(unittest.TestCase):
    def test_portable_records_match_packages_json_on_every_platform(self):
        """Each automatic portable record projects packages.json unchanged."""
        for tool in TOOLS:
            package = TOOL_PACKAGE_ALIASES.get(tool, tool)
            for platform in PLATFORMS:
                record = TOOL_MANIFEST[tool]["platforms"][platform]
                if record["status"] != "automatic":
                    continue
                if record["method"] in _ARCHIVE_METHODS:
                    with self.subTest(tool=tool, platform=platform):
                        resolved = _resolve_like_packages_py(_SPECS[package], platform)
                        self.assertIsNotNone(resolved)
                        spec, binary = resolved
                        self.assertEqual(record["method"], spec["kind"])
                        self.assertEqual(record["version"], spec["version"])
                        self.assertEqual(record["artifact"]["url"], spec["url"])
                        self.assertEqual(record["artifact"]["sha256"], spec["sha256"])
                        self.assertEqual(record["artifact"]["binary"], binary)
                elif record["method"] == "pip":
                    with self.subTest(tool=tool, platform=platform):
                        self.assertEqual(record["python_package"], _SPECS[package]["package"])
                        self.assertEqual(record["version"], _SPECS[package]["version"])

    def test_portable_records_match_live_packages_py_on_current_platform(self):
        """On the running platform, records equal desktop/packages.py resolution."""
        key = packages.platform_key()
        self.assertIn(key, PLATFORMS)
        for tool in TOOLS:
            package = TOOL_PACKAGE_ALIASES.get(tool, tool)
            record = TOOL_MANIFEST[tool]["platforms"][key]
            if record["status"] != "automatic" or record["method"] not in _ARCHIVE_METHODS:
                continue
            with self.subTest(tool=tool, platform=key):
                self.assertTrue(packages.can_install(package))
                spec = packages.package_spec(package)
                self.assertEqual(record["artifact"]["url"], spec["url"])
                self.assertEqual(record["artifact"]["sha256"], spec["sha256"])
                self.assertEqual(record["artifact"]["binary"], spec["binary"])
                # The in-test mirror must track packages.py, so cross-platform
                # assertions above rest on the same resolution rules.
                resolved = _resolve_like_packages_py(_SPECS[package], key)
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved[1], spec["binary"])

    def test_linux_system_package_records_match_the_canonical_table(self):
        """system-package records project PACKAGE_NAMES and its bridge copy."""
        for tool in TOOLS:
            for platform in ("linux-x86_64", "linux-aarch64"):
                record = TOOL_MANIFEST[tool]["platforms"][platform]
                if record.get("method") != "system-package":
                    continue
                with self.subTest(tool=tool, platform=platform):
                    expected = {manager: mapping[tool]
                                for manager, mapping in PACKAGE_NAMES.items()
                                if tool in mapping}
                    self.assertEqual(dict(record["packages"]), expected)
                    for manager in record["instructions"]:
                        self.assertEqual(record["packages"][manager],
                                         BRIDGE_PACKAGE_NAMES[manager][tool])

    def test_linux_auto_capability_agrees_with_the_cli_installer(self):
        """For all 46 tools, manifest and CLI engine agree Linux is automatic."""
        for tool in TOOLS:
            binary = TOOLS[tool]["binary"]
            record = TOOL_MANIFEST[tool]["platforms"]["linux-x86_64"]
            with self.subTest(tool=tool, binary=binary):
                self.assertEqual(record["status"] == "automatic",
                                 _installer_auto_on_linux(binary))

    def test_apt_name_divergences_with_the_cli_installer_are_documented(self):
        """The manifest and the CLI installer disagree on exactly these apt names.

        These are pre-existing, deliberate divergences between two separate
        tables; the single-source work must not erase them by changing a
        capability. amass/bettercap/wpscan: the manifest records a Kali apt
        package while ``core/installer.py`` installs them via go/gem on Linux.
        ettercap: text-only (manifest) vs graphical (installer) apt package.
        """
        documented = {"amass", "bettercap", "ettercap", "wpscan"}
        divergent = set()
        for tool in TOOLS:
            record = TOOL_MANIFEST[tool]["platforms"]["linux-x86_64"]
            if record.get("method") != "system-package":
                continue
            binary = TOOLS[tool]["binary"]
            manifest_apt = record["packages"].get("apt")
            installer_tuple = installer.PKG_NAMES.get(binary)
            installer_apt = installer_tuple[1] if installer_tuple else None
            if manifest_apt != installer_apt:
                divergent.add(tool)
        self.assertEqual(divergent, documented)


if __name__ == "__main__":
    unittest.main()
