from core import ui

TOOLS = ["nmap", "rustscan", "masscan", "naabu"]


def run():
    ui.category_menu("Network Scan", TOOLS)
