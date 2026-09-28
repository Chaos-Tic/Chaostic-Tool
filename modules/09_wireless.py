from core import ui

from core.phases import PHASES

TOOLS = PHASES[8]["tools"]


def run():
    ui.category_menu("Wireless Security", TOOLS)
