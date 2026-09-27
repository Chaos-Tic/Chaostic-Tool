"""Standalone POSIX bridge. JSON stdin control; a real PTY for tool interaction.

This file is also sent as constant Python source to configured SSH hosts. It has
no dependency on Qt, ChaosticTool imports, a personal host, or a shell command.
"""
import errno
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import sys
import time

def emit(value):
    print(json.dumps(value,ensure_ascii=False),flush=True)

def inventory(request):
    found={}
    for key,candidates in request.get('tools',{}).items():
        for name in candidates:
            path=shutil.which(name)
            if path:
                found[key]=path
                break
    interfaces=[]
    if Path('/sys/class/net').is_dir(): interfaces=sorted(p.name for p in Path('/sys/class/net').iterdir())
    emit({'tools':found,'interfaces':interfaces,'uid':os.geteuid(),'python':sys.version.split()[0],
          'apt':bool(shutil.which('apt-get')),'platform':sys.platform,'home':str(Path.home())})
    return 0

def stop_group(pid):
    try: os.killpg(pid,signal.SIGTERM)
    except ProcessLookupError: return
    except PermissionError: return
    time.sleep(.2)
    try: os.killpg(pid,signal.SIGKILL)
    except (ProcessLookupError,PermissionError): pass

def run(request):
    argv=request['argv']
    if not argv or not all(isinstance(x,str) and '\0' not in x for x in argv): raise ValueError('Invalid argument vector')
    directory=request.get('cwd')
    if directory:
        directory=Path(directory).expanduser()
    else:
        import uuid
        directory=Path.home()/'.local/share/ChaosticTool/runs'/uuid.uuid4().hex
    directory.mkdir(parents=True,exist_ok=True)
    if request.get('elevate') and os.geteuid()!=0:
        argv=['sudo','-S','-p','Mot de passe sudo : ','--',*argv]
    pid,master=pty.fork()
    if pid==0:
        try:
            os.chdir(directory)
            os.environ.update(TERM='xterm-256color',PYTHONUNBUFFERED='1',NO_COLOR='1')
            os.execvp(argv[0],argv)
        except BaseException as exc:
            print(str(exc),flush=True)
            os._exit(127)
    import fcntl,struct,termios
    fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',30,120,0,0))
    buffer=b''
    status=None
    deadline=time.monotonic()+request.get('timeout',1200)
    try:
        while True:
            if time.monotonic()>deadline: stop_group(pid); return 124
            readable,_,_=select.select([master,0],[],[],.1)
            if 0 in readable:
                data=os.read(0,65536)
                if not data: stop_group(pid); return 130
                buffer+=data
                if len(buffer)>2_000_000: raise ValueError('Control message too large')
                while b'\n' in buffer:
                    line,buffer=buffer.split(b'\n',1)
                    command=json.loads(line)
                    op=command.get('op')
                    if op=='input': os.write(master,command.get('text','').encode('utf-8'))
                    elif op=='interrupt': os.write(master,b'\x03')
                    elif op=='eof': os.write(master,b'\x04')
                    elif op=='stop': stop_group(pid); return 130
            if master in readable:
                try: data=os.read(master,65536)
                except OSError as exc:
                    if exc.errno!=errno.EIO: raise
                    data=b''
                if data:
                    os.write(1,data)
                else:
                    _,status=os.waitpid(pid,0)
                    break
            child,child_status=os.waitpid(pid,os.WNOHANG) if status is None else (0,0)
            if child:
                status=child_status
                while select.select([master],[],[],0)[0]:
                    try:
                        data=os.read(master,65536)
                        if not data: break
                        os.write(1,data)
                    except OSError: break
                break
        return os.waitstatus_to_exitcode(status)
    finally:
        stop_group(pid)
        os.close(master)
        try: os.waitpid(pid,0)
        except ChildProcessError: pass

def main():
    # Read exactly the initial line: buffered readers could consume control input.
    request=bytearray()
    while not request.endswith(b'\n'):
        chunk=os.read(0,1)
        if not chunk: return 2
        request.extend(chunk)
        if len(request)>2_000_000: raise ValueError('Request too large')
    data=json.loads(request)
    return inventory(data) if data.get('op')=='inventory' else run(data)

if __name__=='__main__':
    try: sys.exit(main())
    except Exception as exc:
        print('Linux bridge: '+str(exc),flush=True)
        sys.exit(1)
