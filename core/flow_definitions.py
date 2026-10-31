"""Shared CLI/Desktop flow definitions; no UI dependencies.

Each step is ``(tool_key, preset_index)`` into ``core.tools.TOOLS``. The built-in
flows are deduplicated on purpose: two steps that run different tools but return
the same information are collapsed to the one that carries the richer, reusable
output, so a flow never pays twice for the same finding. The one intentional
overlap that is kept is cross-validation (``amass`` + ``subfinder`` pull
subdomains from different sources); it is spelled out in the flow description so
it reads as a deliberate choice, not a leftover duplicate.
"""
FLOWS = {'1': {'name': 'Basic attack flow',
       'desc': 'low-noise first pass: DNS A record, passive subdomains, quick ports, '
               'httpx fingerprint (title/tech/status), default nuclei',
       'steps': [('dig', 0),        # authoritative apex A record(s) — cheap, unique, zero-noise
                 ('subfinder', 0),
                 ('nmap', 0),
                 ('httpx', 1),      # single web fingerprint: probe + title + tech + status
                 ('nuclei', 0)]},
 '2': {'name': 'Intermediate attack flow',
       'desc': 'broader recon with crawling and URL history: subdomains, full ports, '
               'httpx, crawl, gau (Wayback + Common Crawl + OTX, subs included), '
               'high/critical nuclei, TLS',
       'steps': [('dig', 0),
                 ('subfinder', 1),
                 ('nmap', 1),       # full-port scan (supersets the former naabu common-port step)
                 ('httpx', 1),
                 ('katana', 1),
                 ('gau', 1),        # --subs supersets the former waybackurls step
                 ('nuclei', 2),
                 ('sslscan', 0)]},
 '3': {'name': 'Advanced attack flow',
       'desc': 'deeper scans; louder and slower, confirm each step. amass + subfinder '
               'cross-validate subdomains from different sources (kept on purpose); '
               'rustscan drives nmap -sC -sV; single dir-buster (ffuf); JS crawl; '
               'high/critical nuclei; TLS; nikto',
       'steps': [('amass', 0),      # cross-validation pair with subfinder (different sources)
                 ('subfinder', 1),
                 ('rustscan', 2),   # full-port rustscan -> nmap -sC -sV (supersets a bare nmap -p-)
                 ('ffuf', 0),       # single dir-buster (gobuster dropped: same dir-brute job)
                 ('katana', 2),
                 ('nuclei', 2),     # merged CVE + high/critical into one high/critical pass
                 ('testssl.sh', 0),
                 ('nikto', 0)]}}
