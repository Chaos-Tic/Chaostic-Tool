from core import ui

TOOLS = ["airmon-ng", "airodump-ng", "aircrack-ng", "reaver", "wifite"]


def run():
    ui.category_menu("Wireless Security", TOOLS)
