from core import ui

from core.phases import PHASES

TOOLS = PHASES[2]["tools"]


def run():
    ui.category_menu("Web Enumeration", TOOLS)
