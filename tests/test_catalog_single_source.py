"""Characterization of the single-source tool catalogue.

Pins the exact phase lists and the exact desktop presets produced by the
per-tool GUI transforms (amass, theharvester, rustscan, dalfox, nuclei), plus
the adjacent hashcat/nmap special cases, so the 'catalog single source'
refactor keeps the catalogue byte-for-byte unchanged. Values were captured from
the pre-refactor catalogue.
"""
import unittest

from core.phases import PHASES, PHASE_DEFS
from core.tools import TOOLS
from desktop.catalog import catalog, build_arguments

EXPECTED_PHASES = [
    {'id': '01_osint', 'name': 'OSINT & reconnaissance passive',
     'tools': ['whois', 'dig', 'subfinder', 'amass', 'dnsrecon', 'theharvester', 'shodan']},
    {'id': '02_recon', 'name': 'Scan réseau',
     'tools': ['nmap', 'rustscan', 'masscan', 'naabu']},
    {'id': '03_web_enum', 'name': 'Énumération Web',
     'tools': ['gobuster', 'ffuf', 'httpx', 'wafw00f', 'whatweb', 'katana', 'gau', 'waybackurls']},
    {'id': '04_vulnscan', 'name': 'Vulnérabilités',
     'tools': ['nikto', 'nuclei', 'wpscan', 'testssl.sh', 'sslscan']},
    {'id': '05_exploitation', 'name': 'Exploitation',
     'tools': ['sqlmap', 'xsstrike', 'dalfox', 'msfconsole', 'msfvenom']},
    {'id': '06_postexploit', 'name': 'Post-exploitation & privilèges',
     'tools': ['secretsdump.py', 'psexec.py', 'crackmapexec']},
    {'id': '07_passwords', 'name': 'Mots de passe',
     'tools': ['hashcat', 'john', 'hydra']},
    {'id': '08_windows', 'name': 'Windows / Active Directory',
     'tools': ['GetUserSPNs.py', 'bloodhound-python']},
    {'id': '09_wireless', 'name': 'Wi-Fi',
     'tools': ['airmon-ng', 'airodump-ng', 'aircrack-ng', 'reaver', 'wifite']},
    {'id': '10_network', 'name': 'Réseau & MITM',
     'tools': ['bettercap', 'ettercap', 'tcpdump', 'responder']},
]

CATALOG_ORDER = [
    'whois', 'dig', 'subfinder', 'amass', 'dnsrecon', 'theharvester', 'shodan', 'nmap',
    'rustscan', 'masscan', 'naabu', 'gobuster', 'ffuf', 'httpx', 'wafw00f', 'whatweb',
    'katana', 'gau', 'waybackurls', 'nikto', 'nuclei', 'wpscan', 'testssl.sh', 'sslscan',
    'sqlmap', 'xsstrike', 'dalfox', 'msfconsole', 'msfvenom', 'secretsdump.py', 'psexec.py',
    'crackmapexec', 'hashcat', 'john', 'hydra', 'GetUserSPNs.py', 'bloodhound-python',
    'airmon-ng', 'airodump-ng', 'aircrack-ng', 'reaver', 'wifite', 'bettercap', 'ettercap',
    'tcpdump', 'responder', 'desktop-diagnostic', 'desktop-dns', 'desktop-http', 'desktop-tls',
]

AMASS = [
    ('Énumération passive (sources par défaut)', ['enum', '-d', '{host}'], {}),
    ('Énumération active (transferts de zone et certificats)',
     ['enum', '-active', '-d', '{host}'], {}),
]

# label, native-args, native-fields, linux-args, linux-fields for the five tools.
TRANSFORMS = {
    'amass': {'native': AMASS, 'linux': AMASS},
    'theharvester': {
        'native': [
            ('Sources publiques crtsh', ['-d', '{host}', '-b', 'crtsh'], {}),
            ('Sources personnalisées', ['-d', '{host}', '-b', '{sources}'],
             {'sources': ('Sources séparées par des virgules', 'crtsh')}),
            ('All sources (slow but complete) · sources configurables', ['-d', '{host}', '-b', '{sources}'],
             {'sources': ('Sources OSINT disponibles', 'crtsh')}),
            ('Google + crtsh + virustotal · sources configurables', ['-d', '{host}', '-b', '{sources}'],
             {'sources': ('Sources OSINT disponibles', 'crtsh')}),
            ('Google only · sources configurables', ['-d', '{host}', '-b', '{sources}'],
             {'sources': ('Sources OSINT disponibles', 'crtsh')}),
        ],
        'linux': [
            ('All sources (slow but complete)', ['-d', '{host}', '-b', 'all'], {}),
            ('Google + crtsh + virustotal', ['-d', '{host}', '-b', 'google,crtsh,virustotal'], {}),
            ('Google only', ['-d', '{host}', '-b', 'google'], {}),
        ],
    },
    'rustscan': {
        'native': [
            ('Port de la cible, sans Nmap', ['-a', '{host}', '-p', '{port}', '--scripts', 'none', '--no-config'], {}),
            ('Quick scan + service detection', ['-a', '{host}', '--', '-sV'], {}),
            ('All ports 1-65535', ['-a', '{host}', '-r', '1-65535'], {}),
            ('With NSE scripts (sC + sV)', ['-a', '{host}', '--', '-sC', '-sV'], {}),
            ('Fast — rate 5000, top 1000 ports', ['-a', '{host}', '-b', '5000', '-r', '1-1000'], {}),
            ('Stealth — rate 500, all ports', ['-a', '{host}', '-b', '500', '-r', '1-65535'], {}),
        ],
        'linux': [
            ('Quick scan + service detection', ['-a', '{host}', '--', '-sV'], {}),
            ('All ports 1-65535', ['-a', '{host}', '-r', '1-65535'], {}),
            ('With NSE scripts (sC + sV)', ['-a', '{host}', '--', '-sC', '-sV'], {}),
            ('Fast — rate 5000, top 1000 ports', ['-a', '{host}', '-b', '5000', '-r', '1-1000'], {}),
            ('Stealth — rate 500, all ports', ['-a', '{host}', '-b', '500', '-r', '1-65535'], {}),
        ],
    },
    'dalfox': {
        'native': [
            ('Analyse de l’URL', ['--no-color', 'scan', '{url}'], {}),
            ('XSS scan on URL', ['scan', '{url}'], {}),
            ('Scan with blind XSS callback', ['scan', '{url}', '--blind', '{callback}'],
             {'callback': ('URL de callback', '')}),
        ],
        'linux': [
            ('XSS scan on URL', ['url', '{url}'], {}),
            ('Scan with blind XSS callback', ['url', '{url}', '--blind', '{callback}'],
             {'callback': ('URL de callback', '')}),
        ],
    },
    'nuclei': {
        'native': [
            ('Vulnérabilités critiques et élevées', ['-u', '{url}', '-severity', 'critical,high', '-rl', '10', '-nc'], {}),
            ('Détection des technologies', ['-u', '{url}', '-tags', 'tech', '-rl', '10', '-nc'], {}),
            ('Default templates (all)', ['-u', '{url}'], {}),
            ('CVEs only', ['-u', '{url}', '-tags', 'cve'], {}),
            ('High and critical severity only', ['-u', '{url}', '-severity', 'high,critical'], {}),
            ('Misconfigurations', ['-u', '{url}', '-tags', 'misconfiguration'], {}),
            ('Exposures (template dir)', ['-u', '{url}', '-tags', 'exposure'], {}),
            ('Network templates', ['-u', '{url}', '-tags', 'network'], {}),
        ],
        'linux': [
            ('Default templates (all)', ['-u', '{url}'], {}),
            ('CVEs only', ['-u', '{url}', '-tags', 'cve'], {}),
            ('High and critical severity only', ['-u', '{url}', '-severity', 'high,critical'], {}),
            ('Misconfigurations', ['-u', '{url}', '-tags', 'misconfiguration'], {}),
            ('Exposures (template dir)', ['-u', '{url}', '-t', 'exposures'], {}),
            ('Network templates', ['-u', '{url}', '-t', 'network'], {}),
        ],
    },
}


def _signature(presets):
    return [(p['label'], list(p.get('args', [])), dict(p.get('fields', {}))) for p in presets]


class CatalogSingleSourceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog()
        self.by_key = {e['key']: e for e in self.catalog}

    def test_phases_are_exact(self):
        self.assertEqual(PHASES, EXPECTED_PHASES)
        self.assertIsInstance(PHASES, list)
        self.assertEqual([p['id'] for p in PHASES], [pid for pid, _name, _cat in PHASE_DEFS])

    def test_phase_membership_is_a_partition_of_tools(self):
        flat = [key for phase in PHASES for key in phase['tools']]
        self.assertEqual(len(flat), len(set(flat)), 'no tool appears in two phases')
        self.assertEqual(set(flat), set(TOOLS))
        self.assertEqual(len(flat), 46)

    def test_phase_is_derived_from_category_with_explicit_overrides(self):
        """Each tool's phase equals its category's phase unless it declares one."""
        category_phase = {cat: pid for pid, _name, cat in PHASE_DEFS if cat}
        phase_of = {key: phase['id'] for phase in PHASES for key in phase['tools']}
        for key, tool in TOOLS.items():
            with self.subTest(key=key):
                expected = tool.get('phase') or category_phase.get(tool['category'])
                self.assertEqual(phase_of[key], expected)

    def test_catalogue_counts_and_order(self):
        self.assertEqual(len(TOOLS), 46)
        self.assertEqual(sum(len(t['presets']) for t in TOOLS.values()), 137)
        self.assertEqual(len(self.catalog), 50)
        self.assertEqual([e['key'] for e in self.catalog], CATALOG_ORDER)
        self.assertEqual(sum(len(e['presets']) for e in self.catalog), 172)
        self.assertEqual(sum(len(e.get('linux_presets', [])) for e in self.catalog), 137)

    def test_gui_transforms_are_exact(self):
        for key, backends in TRANSFORMS.items():
            entry = self.by_key[key]
            with self.subTest(tool=key, backend='native'):
                self.assertEqual(_signature(entry['presets']), backends['native'])
            with self.subTest(tool=key, backend='linux'):
                self.assertEqual(_signature(entry['linux_presets']), backends['linux'])

    def test_hashcat_22000_field_caption_is_native_linux_specific(self):
        hashcat = self.by_key['hashcat']
        native = next(p for p in hashcat['presets'] if '22000' in p['args'])
        linux = next(p for p in hashcat['linux_presets'] if '22000' in p['args'])
        self.assertEqual(native['fields']['hashfile'], ('Fichier de hachages', ''))
        self.assertEqual(linux['fields']['hashfile'], ('Capture de hachages au format 22000', ''))

    def test_nmap_injects_dash6_for_ipv6_targets_only(self):
        nmap = self.by_key['nmap']
        preset = nmap['presets'][0]
        ipv6 = build_arguments(nmap, 0, {'host': '2001:db8::1'}, preset=preset)
        ipv4 = build_arguments(nmap, 0, {'host': '192.0.2.1'}, preset=preset)
        self.assertEqual(ipv6[0], '-6')
        self.assertNotIn('-6', ipv4)


if __name__ == '__main__':
    unittest.main()
