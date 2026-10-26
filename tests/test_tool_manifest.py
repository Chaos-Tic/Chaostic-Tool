"""A4 contract: every catalog tool has safe, actionable installation metadata."""
from __future__ import annotations

import re
import unittest

from core.tool_manifest import (
    PACKAGE_NAMES,
    PLATFORMS,
    TECHNICAL_COMPONENTS,
    TOOL_MANIFEST,
    TOOL_PACKAGE_ALIASES,
)
from core.tools import TOOLS
from desktop.linux_install import PACKAGE_NAMES as LEGACY_PACKAGE_NAMES


class ToolManifestTests(unittest.TestCase):
    def test_manifest_covers_exactly_the_48_catalog_tools(self):
        self.assertEqual(len(TOOLS), 48)
        self.assertEqual(set(TOOL_MANIFEST), set(TOOLS))
        self.assertFalse(set(TOOL_MANIFEST) & TECHNICAL_COMPONENTS)
        for key, record in TOOL_MANIFEST.items():
            with self.subTest(tool=key):
                self.assertEqual(record["tool"], key)
                self.assertEqual(set(record["platforms"]), set(PLATFORMS))

    def test_automatic_sources_are_pinned_and_archives_have_hashes(self):
        archive_methods = {"release", "file", "installer", "pip-source"}
        for tool, tool_record in TOOL_MANIFEST.items():
            for platform, record in tool_record["platforms"].items():
                with self.subTest(tool=tool, platform=platform):
                    if record["status"] != "automatic":
                        continue
                    self.assertIn("version", record)
                    serialized = repr(record).lower()
                    self.assertNotIn("@latest", serialized)
                    self.assertNotIn("@master", serialized)
                    self.assertNotIn("/releases/latest/", serialized)
                    if record["method"] in archive_methods:
                        artifact = record["artifact"]
                        self.assertTrue(artifact["url"].startswith("https://"))
                        self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
                        self.assertTrue(artifact["binary"])

    def test_unsupported_platforms_explain_the_gap_and_next_action(self):
        for tool, tool_record in TOOL_MANIFEST.items():
            for platform, record in tool_record["platforms"].items():
                if record["status"] != "unsupported":
                    continue
                with self.subTest(tool=tool, platform=platform):
                    self.assertTrue(record["reason"].strip())
                    self.assertTrue(record["instruction"].strip())
                    self.assertTrue("`" in record["instruction"] or
                                    "upstream documentation" in record["instruction"])

    def test_grouped_upstream_packages_keep_expected_aliases(self):
        self.assertEqual(set(TOOL_PACKAGE_ALIASES),
                         {"secretsdump.py", "psexec.py", "GetUserSPNs.py"})
        for tool in TOOL_PACKAGE_ALIASES:
            self.assertEqual(TOOL_MANIFEST[tool]["package_alias"], "impacket")
            automatic = [record for record in TOOL_MANIFEST[tool]["platforms"].values()
                         if record["status"] == "automatic"]
            self.assertTrue(automatic)
            self.assertTrue(all(record.get("package") == "impacket" or
                                record["method"] == "system-package"
                                for record in automatic))

    def test_distribution_package_commands_use_declared_package_names(self):
        command_pattern = re.compile(r"^sudo (?:apt install|pacman -S|dnf install) [\w.+-]+$")
        for tool, tool_record in TOOL_MANIFEST.items():
            for platform, record in tool_record["platforms"].items():
                if record["method"] != "system-package":
                    continue
                with self.subTest(tool=tool, platform=platform):
                    self.assertEqual(record["version"], "distribution-managed")
                    self.assertTrue(record["packages"])
                    for manager, command in record["instructions"].items():
                        self.assertIn(manager, record["packages"])
                        self.assertRegex(command, command_pattern)

    def test_standalone_linux_bridge_copy_matches_the_canonical_table(self):
        self.assertEqual({manager: dict(packages)
                          for manager, packages in PACKAGE_NAMES.items()},
                         LEGACY_PACKAGE_NAMES)


if __name__ == "__main__":
    unittest.main()
