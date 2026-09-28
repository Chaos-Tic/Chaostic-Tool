from core import ui

from core.phases import PHASES

TOOLS = PHASES[7]["tools"]


def run():
    ui.category_menu("Windows / Active Directory", TOOLS)
