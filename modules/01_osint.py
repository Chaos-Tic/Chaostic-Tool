from core import ui

from core.phases import PHASES

TOOLS = PHASES[0]["tools"]


def run():
    ui.category_menu("OSINT & Passive Reconnaissance", TOOLS)
