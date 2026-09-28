"""Small bundled diagnostics. Executed in a child process, never in the UI thread."""
import contextlib
from http.client import HTTPConnection, HTTPSConnection
import json
import platform
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import urlsplit


def diagnostic(target):
    from desktop import VERSION
    print(f"ChaosticTool Desktop {VERSION}")
    print(f"Système : {platform.system()} {platform.release()}")
    print(f"Architecture : {platform.machine()}")
    print(f"Python embarqué : {platform.python_version()}")
    print(f"Distribution : {'application autonome' if getattr(sys, 'frozen', False) else 'code source'}")
    print("\nMoteur de diagnostic opérationnel.")
    print("Aucune connexion réseau n’a été effectuée.")


def dns(target):
    host = target["host"]
    print(f"Résolution système de {host}\n", flush=True)
    results = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    for family, address in sorted({("IPv6" if row[0] == socket.AF_INET6 else "IPv4", row[4][0]) for row in results}):
        print(f"{family:5}  {address}")


def http(target):
    url = urlsplit(target["url"])
    cls = HTTPSConnection if url.scheme == "https" else HTTPConnection
    connection = cls(url.hostname, url.port, timeout=12)
    path = url.path or "/"
    if url.query:
        path += "?" + url.query
    print(f"HEAD {target['url']}\n", flush=True)
    try:
        connection.request("HEAD", path, headers={"User-Agent": "ChaosticTool-Desktop/0.1", "Connection": "close"})
        response = connection.getresponse()
        print(f"HTTP {response.status} {response.reason}")
        for name, value in response.getheaders():
            print(f"{name}: {value}")
        if 300 <= response.status < 400:
            print("\nRedirection affichée, sans suivi automatique.")
    finally:
        connection.close()


def tls(target):
    host, port = target["host"], target["port"]
    print(f"Connexion TLS à {host}:{port}\n", flush=True)
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=12) as raw:
        with context.wrap_socket(raw, server_hostname=host) as connection:
            certificate = connection.getpeercert()
            print(f"Protocole : {connection.version()}")
            print(f"Chiffrement : {connection.cipher()[0]}")
            for key in ("subject", "issuer", "notBefore", "notAfter", "subjectAltName"):
                print(f"{key} : {certificate.get(key, '—')}")
            print("\nChaîne de confiance et nom d’hôte validés par le système.")


def whois(target):
    host=target['host']
    def query(server):
        with socket.create_connection((server,43),timeout=10) as connection:
            connection.settimeout(10)
            connection.sendall((host+'\r\n').encode('idna'))
            output=bytearray()
            while len(output)<2_000_000:
                data=connection.recv(65536)
                if not data: break
                output.extend(data)
            return output.decode('utf-8',errors='replace')
    text=query('whois.iana.org')
    print(text,flush=True)
    import re
    match=re.search(r'(?im)^(?:refer|whois):\s*([a-z0-9.-]+)\s*$',text)
    if match:
        server=match.group(1)
        print('\nServeur de référence : '+server+'\n',flush=True)
        print(query(server))


def dig(target):
    import dns.resolver,dns.query,dns.zone
    record=target.get('rrtype','A')
    resolver=dns.resolver.Resolver()
    resolver.lifetime=12
    nameserver=target.get('fields',{}).get('nameserver','')
    if nameserver:
        import ipaddress
        ipaddress.ip_address(nameserver)
        resolver.nameservers=[nameserver]
    print(f"DNS {target['host']} {record}",flush=True)
    if record=='AXFR':
        if not nameserver: raise ValueError('Indiquez l’adresse IP du serveur DNS autoritatif pour un transfert AXFR.')
        zone=dns.zone.from_xfr(dns.query.xfr(nameserver,target['host'],lifetime=15))
        print(zone.to_text())
    else:
        answer=resolver.resolve(target['host'],record)
        for row in answer: print(row.to_text())


def main(arguments):
    worker, request_path, output_path = arguments
    # A direct file stream also works in a frozen, windowless Windows executable.
    with Path(output_path).open("w", encoding="utf-8", buffering=1) as stream:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            try:
                request = json.loads(Path(request_path).read_text(encoding="utf-8"))
                if worker == 'install':
                    from desktop.packages import install_request
                    install_request(request['target'])
                elif worker=='linux-check':
                    from desktop.backends import inspect_backend
                    inspect_backend(request['target'])
                elif worker=='wsl-setup':
                    from desktop.wsl_setup import prepare
                    prepare(request['target'])
                else:
                    {"diagnostic": diagnostic, "dns": dns, "http": http, "tls": tls,'whois':whois,'dig':dig}[worker](request.get("target"))
                return 0
            except Exception as exc:
                print(f"\nErreur : {exc}")
                return 1
