from core import ui

from core.phases import PHASES

TOOLS = PHASES[1]["tools"]


def run():
    ui.category_menu("Network Scan", TOOLS)
