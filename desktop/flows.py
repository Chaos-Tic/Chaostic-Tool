"""Guided CLI-compatible flows, persisted without commands or credentials."""
import copy,json,uuid
from pathlib import Path
from core.flow_definitions import FLOWS
from core.tools import TOOLS
from desktop.storage import write_json,now

def validate_flow(value):
    if not isinstance(value,dict): raise ValueError('Flow invalide.')
    name=value.get('name','')
    if not isinstance(name,str): raise ValueError('Nom de flow invalide.')
    name=name.strip()
    if not name or len(name)>120: raise ValueError('Nom requis (120 caractères maximum).')
    steps=value.get('steps')
    if not isinstance(steps,list) or not 1<=len(steps)<=100: raise ValueError('Un flow doit contenir de 1 à 100 étapes.')
    clean=[]
    for step in steps:
        if not isinstance(step,(list,tuple)) or len(step)!=2: raise ValueError('Étape invalide.')
        key,index=step
        if not isinstance(key,str) or key not in TOOLS or type(index) is not int or not 0<=index<len(TOOLS[key]['presets']):
            raise ValueError(f'Outil ou profil CLI introuvable : {key} / {index}')
        clean.append([key,index])
    result=dict(name=name,desc=str(value.get('desc',''))[:1000],steps=clean)
    # Preserve the optional auto-export marker so the Desktop runner honours a
    # built-in flow's end-of-run export exactly as the CLI does (parity). Only a
    # non-empty string survives; the runner acts solely on the ones it knows.
    export=value.get('export')
    if isinstance(export,str) and export.strip(): result['export']=export.strip()
    return result

def load_flows(root):
    result={key:validate_flow(value) for key,value in FLOWS.items()}
    path=Path(root)/'flows/custom.json'
    if path.exists():
        data=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data,dict): raise ValueError('Fichier de flows personnalisés invalide.')
        result.update({key:validate_flow(value) for key,value in data.items() if key.startswith('custom-')})
    return result

def save_custom(root,flow,key=None):
    flow=validate_flow(flow); key=key or 'custom-'+uuid.uuid4().hex[:10]
    if not key.startswith('custom-'): raise ValueError('Les flows fournis ne sont pas modifiables.')
    all_flows=load_flows(root); all_flows[key]=flow
    write_json(Path(root)/'flows/custom.json',{k:v for k,v in all_flows.items() if k.startswith('custom-')})
    return key

def import_flows(root,path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    values=[data] if isinstance(data,dict) and 'steps' in data else list(data.values()) if isinstance(data,dict) else []
    if not values or len(values)>100: raise ValueError('Aucun flow importable (100 maximum).')
    checked=[validate_flow(v) for v in values]  # validate the entire import first
    all_flows=load_flows(root); keys=[]
    for value in checked:
        key='custom-'+uuid.uuid4().hex[:10]; all_flows[key]=value; keys.append(key)
    write_json(Path(root)/'flows/custom.json',{k:v for k,v in all_flows.items() if k.startswith('custom-')})
    return keys

def step_tool(tool,index):
    """Select by CLI identity, never by a coincidentally matching Desktop index."""
    result=copy.deepcopy(tool)
    result['linux_presets']=[p for p in result.get('linux_presets',[]) if p.get('cli_index')==index]
    if tool['mode']=='builtin':
        if tool['key']=='dig':
            rrtype=TOOLS['dig']['presets'][index]['cmd'][2]
            result['presets']=[p for p in result['presets'] if p.get('rrtype')==rrtype]
    elif tool['mode']=='native': result['presets']=[p for p in result['presets'] if p.get('cli_index')==index]
    else: result['presets']=result['linux_presets']
    if not result['presets']: raise ValueError('Ce profil CLI ne possède pas encore d’adaptateur exécutable.')
    return result

class FlowSession:
    def __init__(self,root,flow,target):
        self.root=Path(root); self.flow=validate_flow(flow)
        # Own a deep copy of the target: the store mutates its target dicts in
        # place (update_target clears and refills the same dict), so a later card
        # edit must not rewrite the target this prepared session already captured.
        self.record=dict(id=uuid.uuid4().hex,name=self.flow['name'],started=now(),target=copy.deepcopy(target),
                         steps=[dict(tool=k,cli_index=i,status='pending') for k,i in self.flow['steps']],status='active')
        self.path=self.root/'flows/history'/(self.record['id']+'.json')
        self.save()
    def save(self): write_json(self.path,self.record)
    def update(self,index,status,run=None):
        self.record['steps'][index]['status']=status
        if run: self.record['steps'][index]['run_id']=run['id']
        self.record['status']='success' if all(s['status'] in ('success','skipped') for s in self.record['steps']) else 'active'
        self.save()

def export_flow_henon(root,flow,record,scope=None):
    """Write the Henon contract (``recon.json``) for a finished flow's runs.

    The CLI reads a per-target results tree; the Desktop keeps each run's output
    under ``runs/<id>/output.txt``, so feed the engine each succeeded step's
    preset ``output`` base paired with that run's text (the same token a CLI
    filename carries). Pure of Qt — the panel calls it in a try/except — so it is
    unit-testable on its own. Returns the written path; ``scope`` defaults to the
    flow's target dict, which carries the Desktop's subdomains/excluded lists."""
    from core import henon_export as henon
    root=Path(root); target=record.get('target') or {}
    pairs=[]
    for step in record.get('steps',[]):
        if not isinstance(step,dict) or step.get('status')!='success': continue
        run_id=step.get('run_id'); key=step.get('tool'); index=step.get('cli_index')
        if not isinstance(run_id,str) or not run_id: continue
        tool=TOOLS.get(key)
        if not tool or type(index) is not int or not 0<=index<len(tool.get('presets',[])): continue
        out_base=tool['presets'][index].get('output')
        if not out_base: continue
        try: text=(root/'runs'/run_id/'output.txt').read_text(encoding='utf-8',errors='replace')
        except OSError: continue
        pairs.append((out_base,text))
    document=henon.from_run_records(target,pairs,target if scope is None else scope)
    return henon.write_export(document,root/'flows'/'history'/(record['id']+'.recon.json'))

