from core import ui

TOOLS = ["hashcat", "john", "hydra"]


def run():
    ui.category_menu("Password Cracking", TOOLS)
