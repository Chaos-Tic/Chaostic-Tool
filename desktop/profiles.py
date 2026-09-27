"""Typed fields and immutable argument vectors shared by all execution backends."""
import ipaddress
import re
import string
from pathlib import Path, PurePosixPath

SECRETS={'passwd','cookie','api_key'}
INPUT_FILES={'hashfile','userfile','capfile','wordlist'}
OUTPUT_FILES={'outfile','pcap'}
CAPTIONS={'passwd':'Mot de passe','cookie':'Cookie de session','api_key':'Clé API','domain':'Domaine','user':'Utilisateur','hashfile':'Fichier de hachages','userfile':'Fichier d’utilisateurs','capfile':'Fichier de capture','outfile':'Fichier de sortie','pcap':'Capture de sortie','iface':'Interface Linux','lhost':'Adresse de retour','lport':'Port de retour','bssid':'BSSID','channel':'Canal','mask':'Masque','fmt':'Format','form':'Formulaire HTTP','callback':'URL de callback','engine':'Moteur Amass','sources':'Sources OSINT','nameserver':'Serveur DNS'}

def placeholders(args):
    return {name for arg in args for _,name,_,_ in string.Formatter().parse(arg) if name}

def normalized(preset, backend='native'):
    result=dict(preset)
    result['args']=list(preset.get('args',preset.get('cmd',[])[1:]))
    fields=dict(preset.get('fields',{}))
    for key,caption in preset.get('prompt',{}).items(): fields.setdefault(key,(CAPTIONS.get(key,caption),''))
    result['fields']=fields
    result['needs_target']=bool(placeholders(result['args']) & {'host','url','port','base_url'})
    result['backend']=backend
    return result

def validate_field(name,value,backend='native'):
    value=value.strip() if name not in SECRETS else value
    if not value or any(ord(c)<32 for c in value): raise ValueError(f'{CAPTIONS.get(name,name)} : valeur requise, sans caractère de contrôle.')
    if name not in SECRETS and value.startswith('-'): raise ValueError('Une valeur ne peut pas commencer par une option (-).')
    if name in INPUT_FILES:
        if backend=='ssh':
            if not PurePosixPath(value).is_absolute(): raise ValueError('Indiquez un chemin Linux absolu sur la machine SSH.')
        elif not Path(value).is_file(): raise ValueError('Fichier introuvable : '+value)
        return value if backend=='ssh' else str(Path(value).resolve())
    if name in OUTPUT_FILES:
        if Path(value).name!=value or '/' in value or '\\' in value or value in ('.','..') or ':' in value: raise ValueError('Choisissez un simple nom de fichier ; la sortie sera dans le dossier de cette opération.')
    if name in ('iface','fmt','domain','user','sources') and not re.fullmatch(r'[\w.@,+\\/-]+',value,re.ASCII): raise ValueError(f'{name} : caractères non autorisés.')
    if name in ('lport','pfilter','channel','size','depth'):
        high=65535 if name in ('lport','pfilter') else 233 if name=='channel' else 10 if name=='depth' else 1_000_000_000
        if not value.isascii() or not value.isdigit() or not (0 if name=='size' else 1)<=int(value)<=high: raise ValueError(f'{name} : valeur numérique invalide.')
    if name in ('target','target1','target2'): ipaddress.ip_address(value)
    if name=='bssid' and not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',value): raise ValueError('BSSID invalide.')
    return value

def secrets_for(preset,values):
    return [values[k] for k in preset.get('fields',{}) if k in SECRETS and values.get(k)]

def redact(text,secrets):
    for secret in sorted(set(secrets),key=len,reverse=True):
        if secret: text=text.replace(secret,'[masqué]')
    return text

class StreamRedactor:
    """Delay a suffix so secrets split across process-output chunks stay hidden."""
    def __init__(self,secrets=()):
        self.secrets=sorted({s.encode('utf-8') for s in secrets if s},key=len,reverse=True)
        self.buffer=b''
        self.keep=max((len(s) for s in self.secrets),default=1)-1
    def feed(self,data,final=False):
        self.buffer+=data
        cutoff=len(self.buffer) if final else max(0,len(self.buffer)-self.keep)
        out=bytearray(); index=0
        while index<cutoff:
            match=next((s for s in self.secrets if self.buffer.startswith(s,index)),None)
            if match: out.extend(b'[masque]'); index+=len(match)
            else: out.append(self.buffer[index]); index+=1
        self.buffer=self.buffer[index:]
        return bytes(out)
