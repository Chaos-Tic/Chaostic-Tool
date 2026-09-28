# Catalogue Desktop 0.4 et compatibilité

Les 48 outils CLI et leurs 137 profils sont référencés. Les quatre utilitaires Desktop portent le catalogue à 52 entrées.

Les dix phases et les trois flows sont partagés avec la CLI. Chaque profil est identifié par son outil et son index CLI : les flows ne dépendent pas de l’ordre différent des profils Desktop. Les adaptateurs natifs peuvent ajouter des profils et adapter les options aux versions distribuées. Amass 5 demande un moteur ; les sources theHarvester sont configurables.

« Natif / intégré » compte les formulaires disponibles, pas les programmes installés. Les profils Linux demandent Linux local, WSL ou SSH. Chaque dépendance a ses propres plateformes, pilotes, services et droits. Les tests construisent les arguments de tous les formulaires ; ils ne réalisent pas toutes ces opérations sur des cibles.

| Outil | Natif / intégré | Linux |
|---|---:|---:|
| Whois | 1 | 1 |
| DNS avancé | 9 | 6 |
| Subfinder | 3 | 2 |
| Amass | 3 | 2 |
| DNSRecon | 2 | 2 |
| theHarvester | 5 | 3 |
| Shodan CLI | 2 | 1 |
| Nmap | 16 | 13 |
| RustScan | 6 | 5 |
| Masscan | 0 | 2 |
| Naabu | 4 | 2 |
| Gobuster | 8 | 7 |
| ffuf | 9 | 7 |
| httpx | 4 | 3 |
| wafw00f | 4 | 2 |
| WhatWeb | 0 | 2 |
| Katana | 6 | 3 |
| gau | 4 | 2 |
| waybackurls | 3 | 1 |
| Nikto | 0 | 2 |
| Nuclei | 8 | 6 |
| WPScan | 0 | 2 |
| testssl.sh | 0 | 3 |
| sslscan | 1 | 1 |
| sqlmap | 6 | 5 |
| XSStrike | 2 | 2 |
| Dalfox | 3 | 2 |
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

Nmap : assistant officiel Windows x64, installation manuelle ou Linux sur les autres plateformes. RustScan : archives officielles Windows x64, Linux x64/ARM64, macOS x64/ARM64 ; Nmap requis pour les profils CLI, profil autonome supplémentaire fourni.

[Guide Windows, installation et limites](../README_WINDOWS.md).
