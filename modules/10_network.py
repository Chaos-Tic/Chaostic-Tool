from core import ui

from core.phases import PHASES

TOOLS = PHASES[9]["tools"]


def run():
    ui.category_menu("Network & MITM", TOOLS)
