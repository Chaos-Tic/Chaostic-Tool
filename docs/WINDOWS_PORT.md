# Suivi du portage Windows

État de Desktop 0.2 : 48 outils d’origine et quatre diagnostics intégrés.

Le compteur « outils prêts » dépend des exécutables installés sur le PC. La validation locale compte 15 outils prêts : quatre diagnostics, dix outils portables et WAFW00F. Ce compteur ne signifie pas que les 48 outils sont portés.

| Outil d’origine | État Windows Desktop | Suite nécessaire |
| --- | --- | --- |
| Whois (`whois`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Dig (`dig`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Subfinder (`subfinder`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| Amass (`amass`) | Service requis | Intégrer et configurer le moteur de collecte Amass 5. |
| DNSRecon (`dnsrecon`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| theHarvester (`theharvester`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Shodan CLI (`shodan`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Nmap (`nmap`) | Adaptateur natif, installation manuelle | Valider la distribution Nmap Windows ; profils TCP connect disponibles. |
| RustScan (`rustscan`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Masscan (`masscan`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Naabu (`naabu`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| Gobuster (`gobuster`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| ffuf (`ffuf`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| httpx (`httpx`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| wafw00f (`wafw00f`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| WhatWeb (`whatweb`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Katana (`katana`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| gau (`gau`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| waybackurls (`waybackurls`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| Nikto (`nikto`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Nuclei (`nuclei`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| WPScan (`wpscan`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| testssl.sh (`testssl.sh`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| sslscan (`sslscan`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| sqlmap (`sqlmap`) | Adaptateur natif, installation non validée sur le poste | Installation bloquée par Defender lors des essais ; aucune protection contournée. |
| XSStrike (`xsstrike`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Dalfox (`dalfox`) | Adaptateur natif et installation intégrée | Maintenir les profils et vérifier les nouvelles versions. |
| Metasploit Console (`msfconsole`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| msfvenom (`msfvenom`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| LinPEAS (`linpeas.sh`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| WinPEAS (`winpeas`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Impacket secretsdump (`secretsdump.py`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Impacket psexec (`psexec.py`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Impacket GetUserSPNs (Kerberoasting) (`GetUserSPNs.py`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| CrackMapExec / NetExec (`crackmapexec`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| BloodHound-python (`bloodhound-python`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Hashcat (`hashcat`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| John the Ripper (`john`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Hydra (`hydra`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| airmon-ng (`airmon-ng`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| airodump-ng (`airodump-ng`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| aircrack-ng (`aircrack-ng`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Reaver (`reaver`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Wifite (`wifite`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Bettercap (`bettercap`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Ettercap (`ettercap`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| tcpdump (`tcpdump`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |
| Responder (`responder`) | À porter | Étudier un adaptateur Windows ou un backend Linux ; ne pas déclarer prêt avant validation. |

## Étapes suivantes

- Compléter les fonctions OSINT/DNS (Whois, requêtes DNS avancées) et les outils locaux compatibles Windows.
- Ajouter les formulaires et adaptations nécessaires aux profils plus complexes, avec gestion des entrées sensibles.
- Traiter séparément les outils interactifs, pilotes réseau et fonctions Wi-Fi : leur présence dans le catalogue ne garantit pas leur exécution sur Windows.
- Étudier le backend Linux/WSL après résolution de son installation sur le poste de validation. Aucun fonctionnement WSL n’est annoncé dans la version 0.2.

## Installer depuis GitHub

La workflow **Windows Desktop** teste et compile le programme sur un runner Windows. Dans **Actions**, ouvrir une exécution réussie et télécharger **ChaosticTool-Windows-Installer** dans les artifacts. Extraire le ZIP puis lancer le fichier Setup. Les artifacts sont conservés 30 jours et leur téléchargement peut nécessiter une connexion GitHub.

Le code, le manifeste des dépendances, les tests et les scripts de fabrication sont versionnés. Les exécutables générés ne sont pas ajoutés à Git. Une release Windows publique permanente reste distincte des artifacts de compilation.
