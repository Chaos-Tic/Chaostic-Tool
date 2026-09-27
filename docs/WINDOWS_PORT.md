# Catalogue Desktop et compatibilité

Les 48 outils CLI sont intégrés. Les 4 diagnostics supplémentaires portent le total à 52.

« Natif » indique un adaptateur disponible ; cela ne garantit pas un binaire distribué pour chaque architecture. Les outils Linux passent par Linux local, WSL ou SSH. Les prérequis et erreurs restent visibles dans l’application.

| Outil | Profils natifs | Profils Linux |
|---|---:|---:|
| Whois | 1 | 1 |
| DNS avancé | 9 | 6 |
| Subfinder | 3 | 2 |
| Amass | 1 | 2 |
| DNSRecon | 2 | 2 |
| theHarvester | 2 | 3 |
| Shodan CLI | 2 | 1 |
| Nmap | 3 | 13 |
| RustScan | 0 | 5 |
| Masscan | 0 | 2 |
| Naabu | 2 | 2 |
| Gobuster | 8 | 7 |
| ffuf | 9 | 7 |
| httpx | 4 | 3 |
| wafw00f | 2 | 2 |
| WhatWeb | 0 | 2 |
| Katana | 3 | 3 |
| gau | 2 | 2 |
| waybackurls | 2 | 1 |
| Nikto | 0 | 2 |
| Nuclei | 8 | 6 |
| WPScan | 0 | 2 |
| testssl.sh | 0 | 3 |
| sslscan | 1 | 1 |
| sqlmap | 6 | 5 |
| XSStrike | 2 | 2 |
| Dalfox | 1 | 2 |
| Metasploit Console | 0 | 1 |
| msfvenom | 0 | 4 |
| LinPEAS | 0 | 1 |
| WinPEAS | 2 | 0 |
| Impacket secretsdump | 1 | 1 |
| Impacket psexec | 1 | 1 |
| Impacket GetUserSPNs (Kerberoasting) | 1 | 1 |
| CrackMapExec / NetExec | 0 | 4 |
| BloodHound-python | 1 | 1 |
| Hashcat | 8 | 8 |
| John the Ripper | 4 | 4 |
| Hydra | 0 | 5 |
| airmon-ng | 0 | 3 |
| airodump-ng | 0 | 2 |
| aircrack-ng | 1 | 1 |
| Reaver | 0 | 1 |
| Wifite | 0 | 2 |
| Bettercap | 0 | 2 |
| Ettercap | 0 | 1 |
| tcpdump | 0 | 4 |
| Responder | 0 | 1 |
| Diagnostic local | 1 | 0 |
| Résolution DNS | 1 | 0 |
| En-têtes HTTP | 1 | 0 |
| Certificat TLS | 1 | 0 |

Les profils sont vérifiés comme vecteurs d’arguments et formulaires. Leur intégration ne constitue pas une validation de toutes leurs fonctions sur des cibles réelles. Les tests automatisés couvrent le lancement, les sorties, les annulations, la persistance et le pont interactif. Voir [le guide](DESKTOP.md) pour les limites par OS et les installations.
