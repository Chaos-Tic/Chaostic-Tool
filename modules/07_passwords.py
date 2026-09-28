from core import ui

from core.phases import PHASES

TOOLS = PHASES[6]["tools"]


def run():
    ui.category_menu("Password Cracking", TOOLS)
