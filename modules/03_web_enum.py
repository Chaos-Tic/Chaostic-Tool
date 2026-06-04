from core import ui

TOOLS = ["gobuster", "ffuf", "httpx", "wafw00f", "whatweb", "katana", "gau", "waybackurls"]


def run():
    ui.category_menu("Web Enumeration", TOOLS)
