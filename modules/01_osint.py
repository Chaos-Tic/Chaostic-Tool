from core import ui

TOOLS = ["whois", "dig", "subfinder", "amass", "dnsrecon", "theharvester", "shodan"]


def run():
    ui.category_menu("OSINT & Passive Reconnaissance", TOOLS)
