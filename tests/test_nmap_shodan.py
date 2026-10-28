"""The Shodan API key feeds the nmap shodan-api profile, redacted at rest."""
import unittest

from core import api_keys
from core.tools import TOOLS
from desktop.catalog import build_arguments, catalog, preset_key_value
from desktop.profiles import redact, secrets_for
from desktop.storage import parse_target


class FakeBackend:
    def __init__(self):
        self.available = True
        self.store = {}

    def get(self, key_id):
        return self.store.get(key_id)

    def set(self, key_id, value):
        self.store[key_id] = value

    def delete(self, key_id):
        self.store.pop(key_id, None)


class NmapShodanTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        api_keys.set_backend(self.backend)

    def tearDown(self):
        api_keys._backend = None
        api_keys._SESSION.clear()

    def _preset(self):
        nmap = next(t for t in catalog() if t["key"] == "nmap")
        return next(p for p in nmap["presets"] if p.get("needs_key") == "shodan"), nmap

    def test_cli_catalog_has_shodan_nmap_profile(self):
        labels = [p for p in TOOLS["nmap"]["presets"] if p.get("needs_key") == "shodan"]
        self.assertEqual(len(labels), 1)
        self.assertIn("shodan-api.apikey={shodan_key}", labels[0]["cmd"])

    def test_desktop_profile_injects_the_key(self):
        api_keys.set_key("shodan", "SECRET-KEY")
        preset, nmap = self._preset()
        args = build_arguments(nmap, 0, parse_target("example.test"), preset=preset)
        self.assertIn("shodan-api.apikey=SECRET-KEY", args)
        self.assertNotIn("{host}", " ".join(args))
        self.assertEqual(preset_key_value(preset), "SECRET-KEY")

    def test_key_is_redacted_for_display_and_history(self):
        api_keys.set_key("shodan", "SECRET-KEY")
        preset, nmap = self._preset()
        args = build_arguments(nmap, 0, parse_target("example.test"), preset=preset)
        redactions = secrets_for(preset, {}) + [preset_key_value(preset)]
        masked = redact(" ".join(args), redactions)
        self.assertNotIn("SECRET-KEY", masked)

    def test_missing_key_builds_empty_without_raising(self):
        preset, nmap = self._preset()
        args = build_arguments(nmap, 0, parse_target("example.test"), preset=preset)
        self.assertIn("shodan-api.apikey=", args)
        self.assertNotIn("SECRET", " ".join(args))
        self.assertIsNone(preset_key_value(preset))


if __name__ == "__main__":
    unittest.main()
