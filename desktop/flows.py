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
    return dict(name=name,desc=str(value.get('desc',''))[:1000],steps=clean)

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
        self.record=dict(id=uuid.uuid4().hex,name=self.flow['name'],started=now(),target=target,
                         steps=[dict(tool=k,cli_index=i,status='pending') for k,i in self.flow['steps']],status='active')
        self.path=self.root/'flows/history'/(self.record['id']+'.json')
        self.save()
    def save(self): write_json(self.path,self.record)
    def update(self,index,status,run=None):
        self.record['steps'][index]['status']=status
        if run: self.record['steps'][index]['run_id']=run['id']
        self.record['status']='success' if all(s['status'] in ('success','skipped') for s in self.record['steps']) else 'active'
        self.save()

