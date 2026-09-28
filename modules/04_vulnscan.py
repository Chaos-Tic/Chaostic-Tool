from core import ui

from core.phases import PHASES

TOOLS = PHASES[3]["tools"]


def run():
    ui.category_menu("Vulnerability Scan", TOOLS)
