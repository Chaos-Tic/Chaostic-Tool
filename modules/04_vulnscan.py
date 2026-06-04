from core import ui

TOOLS = ["nikto", "nuclei", "wpscan", "testssl.sh", "sslscan"]


def run():
    ui.category_menu("Vulnerability Scan", TOOLS)
