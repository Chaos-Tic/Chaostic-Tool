from core import ui

TOOLS = ["bettercap", "ettercap", "tcpdump", "responder"]


def run():
    ui.category_menu("Network & MITM", TOOLS)
