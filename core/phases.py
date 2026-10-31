"""Phase order and tool membership shared by CLI and Desktop.

Membership is derived from the single tool catalogue in :mod:`core.tools`
instead of being re-declared here: adding or removing a tool means editing
``core/tools.py`` only, and the phases below rebuild from it. Each tool is
placed by its ``category``; a tool that belongs to a phase which is not a plain
rename of its category carries an explicit ``phase`` key (e.g. the Active
Directory tools, a hand-picked subset of the ``postexploit`` category, declare
``"phase": "08_windows"``).

``PHASE_DEFS`` holds only the presentation and ordering: the phase id, its
French display name, and the category it collects by default. Phase order is the
list order and is load-bearing — consumers index ``PHASES[0..9]`` by position.
``08_windows`` has no default category (``None``); its members arrive solely via
the tools' explicit ``phase`` key.
"""
from core.tools import TOOLS

PHASE_DEFS = [
    ('01_osint', 'OSINT & reconnaissance passive', 'osint'),
    ('02_recon', 'Scan réseau', 'recon'),
    ('03_web_enum', 'Énumération Web', 'web_enum'),
    ('04_vulnscan', 'Vulnérabilités', 'vulnscan'),
    ('05_exploitation', 'Exploitation', 'exploitation'),
    ('06_postexploit', 'Post-exploitation & privilèges', 'postexploit'),
    ('07_passwords', 'Mots de passe', 'passwords'),
    ('08_windows', 'Windows / Active Directory', None),
    ('09_wireless', 'Wi-Fi', 'wireless'),
    ('10_network', 'Réseau & MITM', 'network'),
]


def _build_phases():
    """Group every tool into its phase, preserving ``TOOLS`` insertion order.

    A tool's phase is its explicit ``phase`` key when present, otherwise the
    phase whose default category matches the tool's ``category``. The result is
    a strict partition of ``TOOLS``: every tool lands in exactly one phase.
    """
    category_phase = {category: pid for pid, _name, category in PHASE_DEFS if category}
    members = {pid: [] for pid, _name, _category in PHASE_DEFS}
    for key, tool in TOOLS.items():
        pid = tool.get('phase') or category_phase.get(tool.get('category'))
        if pid not in members:
            raise ValueError(
                f"tool {key!r} resolves to no phase "
                f"(category={tool.get('category')!r}, phase={tool.get('phase')!r})")
        members[pid].append(key)
    return [{'id': pid, 'name': name, 'tools': members[pid]} for pid, name, _category in PHASE_DEFS]


PHASES = _build_phases()
